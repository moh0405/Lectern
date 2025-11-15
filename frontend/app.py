import os
import sys
from pathlib import Path
from typing import List, Dict, Any

import streamlit as st

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.source_manager import detect_source_type, process_url, process_file


def _save_uploaded_file(file) -> Path:
    out_dir = PROJECT_ROOT / "data" / "uploaded_files"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / file.name
    dest.write_bytes(file.getbuffer())
    return dest


def _format_ts(seconds: float | None) -> str:
    if seconds is None:
        return ""
    s = int(seconds)
    return f"{s//60}:{s%60:02d}"


def build_ui():
    st.set_page_config(page_title="AI Study Mentor — Multi-Source", layout="wide")
    st.title("AI Study Mentor — Multi-Source Ingest")
    st.caption("Paste URLs or upload audio/video/PDF, process entirely from the frontend.")

    if "sources" not in st.session_state:
        st.session_state["sources"] = []  # list of {id, type, title, icon, chunks}

    # Sidebar unified ingest
    with st.sidebar:
        with st.expander("📚 Add Content", expanded=True):
            uploaded_files = st.file_uploader(
                "Upload files (PDF, MP3, MP4, WAV)", accept_multiple_files=True,
                type=["pdf", "mp3", "mp4", "wav", "m4a"],
            )
            urls_text = st.text_area(
                "Or paste URLs (one per line)",
                placeholder="https://youtube.com/watch?v=xyz\nhttps://github.com/user/repo\nhttps://example.com/article",
            )

            if st.button("🔮 Process All"):
                # Process uploads
                if uploaded_files:
                    for f in uploaded_files:
                        size_mb = len(f.getbuffer()) / (1024 * 1024)
                        if size_mb > 25:
                            st.warning(f"Skipping {f.name}: exceeds 25MB")
                            continue
                        st.info(f"Uploading {f.name} ({size_mb:.2f} MB)…")
                        dest = _save_uploaded_file(f)
                        st.write("Processing…")
                        try:
                            stype = detect_source_type(dest.name)
                            if stype == "audio":
                                chunks = process_file(str(dest))
                                title = dest.name
                                icon = "🎧"
                            else:
                                # PDFs saved for offline processing; not chunked here
                                chunks = []
                                title = dest.name
                                icon = "📄" if dest.suffix.lower() == ".pdf" else "📦"
                            st.session_state["sources"].append({
                                "id": f"file-{dest.name}",
                                "type": stype,
                                "title": title,
                                "icon": icon,
                                "chunks": chunks,
                            })
                            st.success(f"Processed {dest.name}")
                        except Exception as e:
                            st.error(f"Failed to process {f.name}: {e}")

                # Process URLs
                urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
                for url in urls:
                    st.info(f"Fetching: {url}")
                    try:
                        stype = detect_source_type(url)
                        chunks = process_url(url)
                        # derive display info
                        icon = {"youtube": "🎬", "web": "📰", "github": "💻"}.get(stype, "🔗")
                        title = url
                        if chunks:
                            # try metadata in extra fields
                            ex = chunks[0].get("extra", {})
                            title = ex.get("title") or chunks[0].get("doc") or title
                        st.session_state["sources"].append({
                            "id": f"url-{len(st.session_state['sources'])}",
                            "type": stype,
                            "title": title,
                            "icon": icon,
                            "chunks": chunks,
                        })
                        st.success(f"Processed {stype} source: {title}")
                    except Exception as e:
                        st.error(f"Failed to process {url}: {e}")

    # Main page: list processed sources and previews
    with st.expander("📂 Sources", expanded=True):
        srcs = st.session_state.get("sources", [])
        if not srcs:
            st.info("No sources yet. Add URLs or upload files from the sidebar.")
        for i, s in enumerate(srcs):
            st.write(f"{s['icon']} {s['title']} — {len(s['chunks'])} chunks")
            if st.button("🗑️ Delete", key=f"del-{i}"):
                # Remove from session list
                st.session_state["sources"].pop(i)
                st.experimental_rerun()
            # Show small previews for first few chunks
            for c in s["chunks"][:3]:
                t = (c.get("text") or "").strip()
                snippet = (t[:240] + ("…" if len(t) > 240 else ""))
                st.caption(snippet)
                if s["type"] == "youtube":
                    ex = c.get("extra", {})
                    ts = _format_ts(ex.get("start"))
                    url = ex.get("citation_url") or c.get("url")
                    dur = ex.get("duration_seconds")
                    dur_s = f" • duration {dur//60}:{dur%60:02d}" if dur else ""
                    st.write(f"See {ts} in video{dur_s}: {url}")
                elif s["type"] == "web":
                    st.write(f"Source: {c.get('url')}")
                elif s["type"] == "github":
                    ex = c.get("extra", {})
                    st.write(f"File: {ex.get('file_path')} • {c.get('url')}")


if __name__ == "__main__":
    build_ui()