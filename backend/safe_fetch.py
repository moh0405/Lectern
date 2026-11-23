"""Fetch a URL a visitor supplied without letting them reach anything private.

Every server-side fetch of a user-supplied URL goes through `safe_get`, which:

  * allows only http(s) on ports 80 and 443, with no credentials in the URL
  * refuses loopback, private, link-local, shared (CGNAT), multicast, reserved and cloud-metadata addresses, including
    IPv4 hidden inside IPv6 (mapped, 6to4, Teredo, NAT64) and odd spellings such as `2130706433` or `0x7f.1`
  * checks the address at connect time, on the socket it then uses, so a name that changes its answer between a check
    and the connection (DNS rebinding) cannot slip through. TLS is still verified against the original host name
  * follows redirects itself (at most MAX_REDIRECTS) and applies all of the above to each hop
  * ignores proxy settings from the environment, which would otherwise make the proxy do the resolving
  * stops at MAX_BYTES of decoded body (so a compression bomb is cut off too) and at MAX_SECONDS overall

What remains: the check cannot know about a private service that is reachable on a public address.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 5 * 1024 * 1024
MAX_SECONDS = 30.0
MAX_REDIRECTS = 5
CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 10.0
ALLOWED_PORTS = {80, 443}

IP = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

_BLOCKED_NAMES = {"localhost", "metadata", "metadata.google.internal", "instance-data"}
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".lan", ".home", ".corp")
# Public-looking addresses that are really platform services.
_BLOCKED_NETS = [ipaddress.ip_network("168.63.129.16/32")]  # Azure's wire server
_NAT64 = [ipaddress.ip_network("64:ff9b::/96"), ipaddress.ip_network("64:ff9b:1::/48")]


class UnsafeUrl(ValueError):
    """The URL is not allowed, or its response broke a limit."""


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> List[ipaddress.IPv4Address]:
    """IPv4 addresses an IPv6 address carries, which is where traffic to it would really go."""
    found: List[ipaddress.IPv4Address] = []
    if ip.ipv4_mapped:
        found.append(ip.ipv4_mapped)
    if ip.sixtofour:
        found.append(ip.sixtofour)
    if ip.teredo:
        found.extend(ip.teredo)
    low32 = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if any(ip in net for net in _NAT64) or int(ip) >> 32 == 0:  # NAT64, or the deprecated IPv4-compatible form
        found.append(low32)
    return found


def ip_allowed(ip: IP) -> bool:
    """True only for an ordinary public unicast address."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.scope_id:
            return False
        inner = _embedded_ipv4(ip)
        if inner:
            return all(ip_allowed(v4) for v4 in inner)
    if ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_private:
        return False
    if any(ip.version == net.version and ip in net for net in _BLOCKED_NETS):
        return False
    return ip.is_global


def _literal_ip(host: str) -> Optional[IP]:
    """The address when `host` is written as one, including the forms C's inet_aton accepts (`127.1`, `0x7f.0.0.1`)."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if host.isascii() and host[-1:].isalnum() and all(p and (p.isdigit() or p.lower().startswith("0x")) for p in host.split(".")):
        try:
            return ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            raise UnsafeUrl("That address is not valid.") from None
    return None


def check_url(url: str) -> Tuple[str, str, int]:
    """(scheme, host, port) if the URL may be fetched, without any network access. Raises UnsafeUrl otherwise."""
    if not isinstance(url, str) or "\\" in url or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url):
        raise UnsafeUrl("That URL contains characters that are not allowed.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise UnsafeUrl("That URL is not valid.") from None
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeUrl("Only http and https URLs can be added.")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrl("URLs with a user name or password cannot be added.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeUrl("That URL has no host.")
    port = port or (443 if scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise UnsafeUrl("Only the standard web ports (80 and 443) are allowed.")
    if host in _BLOCKED_NAMES or host.endswith(_BLOCKED_SUFFIXES):
        raise UnsafeUrl("That URL points to a private address.")
    literal = _literal_ip(host)
    if literal is not None and not ip_allowed(literal):
        raise UnsafeUrl("That URL points to a private address.")
    return scheme, host, port


def resolve_public(host: str, port: int) -> List[Tuple[int, Tuple[Any, ...]]]:
    """(family, sockaddr) for every address of `host`. If any address is not public, the whole name is refused."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as e:
        raise UnsafeUrl(f"Could not resolve {host}.") from e
    targets = [(info[0], info[4]) for info in infos]
    if not targets:
        raise UnsafeUrl(f"Could not resolve {host}.")
    for _family, sockaddr in targets:
        if not ip_allowed(ipaddress.ip_address(str(sockaddr[0]).split("%")[0])) or "%" in str(sockaddr[0]):
            raise UnsafeUrl("That URL points to a private address.")
    return targets


def _connect(host: str, port: int, timeout: Any, options: Any) -> socket.socket:
    """A socket connected to a public address of `host`; the address checked is the address used."""
    wait = timeout if isinstance(timeout, (int, float)) else CONNECT_TIMEOUT_S
    last: Optional[OSError] = None
    for family, sockaddr in resolve_public(host, port):
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            for option in options or []:
                sock.setsockopt(*option)
            sock.settimeout(wait)
            sock.connect(sockaddr)
            return sock
        except OSError as e:
            last = e
            sock.close()
    raise last or OSError(f"Could not connect to {host}")


_session_factory: Any = None


def _build_session_factory() -> Any:
    """Built on first use: the HTTP libraries are slow to import and server startup has a hard limit on Lambda."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3 import HTTPConnectionPool, HTTPSConnectionPool, PoolManager
    from urllib3.connection import HTTPConnection, HTTPSConnection

    class Plain(HTTPConnection):
        def _new_conn(self) -> socket.socket:
            return _connect(self._dns_host, self.port, self.timeout, self.socket_options)

    class Secure(HTTPSConnection):
        def _new_conn(self) -> socket.socket:
            return _connect(self._dns_host, self.port, self.timeout, self.socket_options)

    class PlainPool(HTTPConnectionPool):
        ConnectionCls = Plain

    class SecurePool(HTTPSConnectionPool):
        ConnectionCls = Secure

    class GuardedAdapter(HTTPAdapter):
        def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **kw: Any) -> None:
            super().init_poolmanager(connections, maxsize, block=block, **kw)
            manager: PoolManager = self.poolmanager
            manager.pool_classes_by_scheme = {"http": PlainPool, "https": SecurePool}

    def factory() -> Any:
        session = requests.Session()
        session.trust_env = False  # a proxy from the environment would resolve names itself
        adapter = GuardedAdapter(max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    return factory


def _read_limited(resp: Any, max_bytes: int, deadline: float) -> bytes:
    declared = resp.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise UnsafeUrl(f"The page is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    body = bytearray()
    while True:
        if time.monotonic() >= deadline:
            raise UnsafeUrl("The page took too long to download.")
        # read1 returns after one socket read, so a server that drips bytes cannot hold this past the deadline.
        piece = resp.raw.read1(64 * 1024, decode_content=True)
        if not piece:
            return bytes(body)
        body += piece
        if len(body) > max_bytes:
            raise UnsafeUrl(f"The page is larger than the {max_bytes // (1024 * 1024)} MB limit.")


def safe_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    max_bytes: int = MAX_BYTES,
    max_seconds: float = MAX_SECONDS,
) -> Any:
    """GET `url` under the rules above. Returns a fully read `requests.Response`; raises UnsafeUrl or a requests error."""
    global _session_factory
    if _session_factory is None:
        _session_factory = _build_session_factory()
    deadline = time.monotonic() + max_seconds
    current = url
    with _session_factory() as session:
        for _hop in range(MAX_REDIRECTS + 1):
            check_url(current)
            left = deadline - time.monotonic()
            if left <= 0:
                raise UnsafeUrl("The page took too long to download.")
            resp = session.get(
                current, params=params, headers=headers, stream=True, allow_redirects=False,
                timeout=(min(CONNECT_TIMEOUT_S, left), min(READ_TIMEOUT_S, left)),
            )
            try:
                if resp.is_redirect:
                    current = urljoin(resp.url, resp.headers["location"])
                    params = None  # they belong to the first URL only
                    continue
                resp._content = _read_limited(resp, max_bytes, deadline)
                resp._content_consumed = True
                return resp
            finally:
                resp.close()
    raise UnsafeUrl("Too many redirects.")


def host_is(url: str, *domains: str) -> bool:
    """True when the URL's host is exactly one of `domains` or a subdomain of one (`youtube.com.evil.test` is not)."""
    try:
        host = (urlsplit(url).hostname or "").rstrip(".").lower()
    except ValueError:
        return False
    return any(host == d or host.endswith("." + d) for d in domains)
