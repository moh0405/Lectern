"""SSRF guard: real sockets against a local server, with the "is this address public?" rule opened only for it."""

import gzip
import http.server
import ipaddress
import socket
import threading
import time

import pytest

import backend.safe_fetch as sf
from backend.document_processor import _detect_source
from backend.safe_fetch import UnsafeUrl, check_url, ip_allowed, safe_get
from backend.source_manager import detect_source_type
from backend.sources.github_source import GitHubSource, _repo_parts
from backend.sources.web_source import WebSource
from backend.sources.youtube_source import YouTubeSource, _parse_video_id


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "100.100.100.200", "0.0.0.0",
    "224.0.0.1", "240.0.0.1", "255.255.255.255", "198.18.0.1", "192.0.2.1", "168.63.129.16",
    "::1", "::", "fe80::1", "fc00::1", "fd00:ec2::254", "ff02::1", "::ffff:127.0.0.1", "::ffff:169.254.169.254",
    "::127.0.0.1", "2002:7f00:1::", "2002:a9fe:a9fe::", "64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe", "2001:0:4136:e378:8000:63bf:80ff:fffe",
])
def test_private_and_special_addresses_are_refused(ip):
    assert not ip_allowed(ipaddress.ip_address(ip))


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"])
def test_public_addresses_are_allowed(ip):
    assert ip_allowed(ipaddress.ip_address(ip))


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/a", "gopher://example.com/", "javascript:alert(1)", "http://", "not a url",
    "http://localhost/", "http://LOCALHOST./", "http://a.localhost/", "http://metadata.google.internal/", "http://db.internal/",
    "http://127.0.0.1/", "http://2130706433/", "http://0x7f.0.0.1/", "http://0177.0.0.1/", "http://127.1/", "http://[::1]/",
    "http://[::ffff:127.0.0.1]/", "http://169.254.169.254/latest/meta-data/", "http://user:pw@example.com/",
    "http://example.com@127.0.0.1/", "http://example.com:22/", "http://example.com:notaport/", "http://evil.test\\@127.0.0.1/",
    "http://exa mple.com/", "http://example.com/\r\nHost: x",
])
def test_bad_urls_are_refused_without_network(url, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("no DNS lookup expected"))
    with pytest.raises(UnsafeUrl):
        check_url(url)


def test_ordinary_urls_pass():
    assert check_url("https://example.com/post?a=1") == ("https", "example.com", 443)
    assert check_url("http://example.com:80/") == ("http", "example.com", 80)


class Handler(http.server.BaseHTTPRequestHandler):
    hits: list = []

    def log_message(self, *a):
        pass

    def _send(self, body, status=200, **headers):
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k.replace("_", "-"), v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Handler.hits.append(self.path)
        if self.path == "/ok":
            self._send(b"<html>hello</html>", Content_Type="text/html; charset=utf-8")
        elif self.path == "/to-ok":
            self._send(b"", 302, Location="/ok")
        elif self.path == "/to-metadata":
            self._send(b"", 302, Location="http://169.254.169.254/latest/meta-data/")
        elif self.path == "/to-file":
            self._send(b"", 302, Location="file:///etc/passwd")
        elif self.path == "/loop":
            self._send(b"", 302, Location="/loop")
        elif self.path == "/huge":
            self._send(b"x" * 2048)
        elif self.path == "/huge-unsized":
            self.send_response(200)
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            for _ in range(8):
                self.wfile.write(b"y" * 1024)
        elif self.path == "/bomb":
            self._send(gzip.compress(b"z" * 1_000_000), Content_Encoding="gzip")
        elif self.path == "/drip":
            self.send_response(200)
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                for _ in range(100):
                    self.wfile.write(b".")
                    self.wfile.flush()
                    time.sleep(0.05)
            except OSError:
                pass


@pytest.fixture
def server(monkeypatch):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    Handler.hits = []
    port = srv.server_address[1]
    real_allowed, real_getaddrinfo = sf.ip_allowed, socket.getaddrinfo
    # Only the test server's name and port are opened; every other rule stays on.
    monkeypatch.setattr(sf, "ALLOWED_PORTS", {80, 443, port})
    monkeypatch.setattr(sf, "ip_allowed", lambda ip: str(ip) == "127.0.0.1" or real_allowed(ip))
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, p, *a, **k: real_getaddrinfo("127.0.0.1" if host == "site.test" else host, p, *a, **k))
    yield f"http://site.test:{port}"
    srv.shutdown()
    srv.server_close()


def test_fetches_a_public_page(server):
    r = safe_get(server + "/ok")
    assert r.status_code == 200 and r.text == "<html>hello</html>"


def test_follows_a_safe_redirect(server):
    assert safe_get(server + "/to-ok").text == "<html>hello</html>"


@pytest.mark.parametrize("path", ["/to-metadata", "/to-file"])
def test_a_redirect_to_a_forbidden_target_is_refused(server, path, monkeypatch):
    with pytest.raises(UnsafeUrl):
        safe_get(server + path)
    assert Handler.hits == [path]


def test_redirect_loops_stop(server):
    with pytest.raises(UnsafeUrl, match="redirects"):
        safe_get(server + "/loop")
    assert len(Handler.hits) == sf.MAX_REDIRECTS + 1


@pytest.mark.parametrize("path", ["/huge", "/huge-unsized", "/bomb"])
def test_body_size_is_capped_even_when_undeclared_or_compressed(server, path):
    with pytest.raises(UnsafeUrl, match="limit"):
        safe_get(server + path, max_bytes=1024)


def test_a_server_that_drips_bytes_hits_the_total_deadline(server):
    t0 = time.monotonic()
    with pytest.raises(UnsafeUrl, match="too long"):
        safe_get(server + "/drip", max_seconds=0.4)
    assert time.monotonic() - t0 < 2


def test_dns_rebinding_is_caught_at_connect_time(server, monkeypatch):
    """The name looks public until the moment of connecting; the address actually dialled is the one checked."""
    port = int(server.rsplit(":", 1)[1])
    monkeypatch.setattr(sf, "ip_allowed", lambda ip: str(ip) != "10.0.0.5")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port))])
    dialled = []
    monkeypatch.setattr(socket.socket, "connect", lambda self, addr: dialled.append(addr))
    with pytest.raises(UnsafeUrl, match="private"):
        safe_get(server + "/ok")
    assert dialled == []


def test_a_name_with_any_private_address_is_refused(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
    ])
    with pytest.raises(UnsafeUrl, match="private"):
        sf.resolve_public("mixed.test", 80)


def test_environment_proxies_are_ignored(monkeypatch):
    if sf._session_factory is None:
        sf._session_factory = sf._build_session_factory()
    assert sf._session_factory().trust_env is False


def test_web_source_refuses_metadata_url(monkeypatch):
    import backend.sources.web_source as web

    monkeypatch.setattr(web, "BeautifulSoup", object)  # the optional scraping libraries are not needed to refuse
    monkeypatch.setattr(web, "Document", object)
    assert WebSource().validate("http://169.254.169.254/") is False
    with pytest.raises(UnsafeUrl):
        WebSource().extract("http://169.254.169.254/latest/meta-data/")


@pytest.mark.parametrize("url", ["http://youtube.com.evil.test/?v=abcdefghijk", "http://evil.test/youtube.com?v=abcdefghijk", "http://169.254.169.254/?x=github.com"])
def test_lookalike_hosts_are_not_treated_as_youtube_or_github(url):
    assert _detect_source(url) == "web" and detect_source_type(url) == "web"
    assert _parse_video_id(url) is None and not YouTubeSource().validate(url)


def test_youtube_only_fetches_its_own_canonical_page(monkeypatch):
    import backend.sources.youtube_source as yt

    seen = []

    class Resp:
        ok, text = True, ""

        def json(self):
            return {"title": "T"}

    monkeypatch.setattr(yt, "safe_get", lambda url, **kw: seen.append((url, kw.get("params"))) or Resp())
    monkeypatch.setattr(yt, "YouTubeTranscriptApi", type("A", (), {"get_transcript": staticmethod(lambda vid: [{"text": "hi", "start": 0, "duration": 1}])}))
    YouTubeSource().extract("https://www.youtube.com/watch?v=abcdefghijk&next=http://169.254.169.254/")
    canonical = "https://www.youtube.com/watch?v=abcdefghijk"
    assert seen == [("https://www.youtube.com/oembed", {"url": canonical, "format": "json"}), (canonical, None)]


@pytest.mark.parametrize("url", ["file://github.com/etc/passwd", "ssh://github.com/a/b", "https://github.com.evil.test/a/b", "https://user@github.com/a/b", "https://github.com/../x", "https://github.com/-upload-pack/b"])
def test_github_urls_are_strict(url):
    assert _repo_parts(url) is None


def test_github_clone_uses_only_the_canonical_https_url(tmp_path, monkeypatch):
    import backend.sources.github_source as gh

    ran = []
    monkeypatch.setattr(gh.subprocess, "run", lambda cmd, **kw: ran.append((cmd, kw)))
    GitHubSource(str(tmp_path))._clone("https://github.com/owner/repo.git?x=--upload-pack=evil")
    cmd, kw = ran[0]
    assert cmd[-2:] == ["https://github.com/owner/repo.git", str(tmp_path / "owner__repo")] and cmd[-3] == "--"
    assert "http.followRedirects=false" in cmd and "protocol.allow=never" in cmd and "--depth=1" in cmd
    assert kw["timeout"] == gh.CLONE_TIMEOUT_S and kw["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_a_repository_symlink_cannot_read_server_files(tmp_path):
    secret = tmp_path / "secret.md"
    secret.write_text("TOP SECRET")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "real.md").write_text("fine")
    (root / "link.md").symlink_to(secret)
    (root / "dir").symlink_to(tmp_path)
    assert [p.name for p in GitHubSource()._iter_files(root)] == ["real.md"]


def test_add_urls_route_refuses_private_targets(api):
    r = api.post("/api/v1/sources/urls", json={"urls": ["http://169.254.169.254/latest/meta-data/"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_url"
