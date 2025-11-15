"""
frontend/app.py — Hackathon Demo UI (production-ready)

Delivers a visually polished, judge-friendly RAG demo:
- WOW: dark theme polish, animated progress, streaming-like responses, toasts
- Visual RAG: side-by-side Question | Context | Answer, color bars, keyword highlights
- Features: multi-file upload, live processing, chat history + markdown export
- Controls: temperature, top-k, model selection
- Stats: chunks, documents, queries count
- Citations: clickable links
- Safety: robust error handling and graceful fallbacks

Note: Keeps dependencies minimal; word-by-word streaming is simulated for UX polish.
"""

import os
import sys
import time
import re
from pathlib import Path
from typing import List, Dict, Any

import streamlit as st

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.rag_engine import RAGEngine
from backend.llm_config import GeminiClient
from backend.document_processor import list_chunks_from_dir


def inject_css():
    """Load custom CSS for polished visuals."""
    css_path = Path(__file__).resolve().parent / "styles.css"
    if css_path.exists():
        try:
            st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
        except Exception:
            pass


def relevance_color(score: float) -> str:
    if score is None:
        return "#64748b"
    if score >= 0.6:
        return "#22c55e"  # green
    if score >= 0.3:
        return "#f59e0b"  # amber
    return "#ef4444"  # red


def keyword_highlights(question: str, text: str) -> str:
    """Wrap overlapping keywords in a highlight span for visual RAG."""
    try:
        q_tokens = set(re.findall(r"\b\w+\b", question.lower()))
        words = re.findall(r"\b\w+\b|\W+", text)
        out = []
        for w in words:
            ww = w.lower()
            if ww.isalpha() and ww in q_tokens:
                out.append(f"<span class='hl'>{w}</span>")
            else:
                out.append(w)
        return "".join(out)
    except Exception:
        return st.html_escape(text)


def chunk_card(chunk: Dict[str, Any], question: str) -> None:
    score = float(chunk.get("score") or 0.0)
    color = relevance_color(score)
    doc = chunk.get("doc", "")
    page = chunk.get("page", None)
    text = (chunk.get("text", "") or "").strip()
    snippet = (text[:500] + ("…" if len(text) > 500 else ""))
    highlighted = keyword_highlights(question, snippet)
    st.markdown(
        f"""
        <div class="chunk-card">
            <div class="chunk-meta">
              <span>{doc}{f' • page {page}' if page else ''}</span>
              <span class="score-bar" style="--score:{score:.2f}; background: {color}">{score:.2f}</span>
            </div>
            <div class="chunk-text">{highlighted}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def toast(msg: str, kind: str = "info"):
    # Streamlit built-in toast for quick feedback
    try:
        st.toast(msg)
    except Exception:
        getattr(st, kind)(msg)


def stats_panel(engine: RAGEngine | None = None) -> Dict[str, Any]:
    try:
        if engine is None:
            engine = RAGEngine(auto_embeddings=False)
        items = engine._docstore_iter()
    except Exception:
        try:
            items = list_chunks_from_dir(str(Path("data/uploaded_files").resolve()))
        except Exception:
            items = []
    docs = sorted({it.get("doc", "") for it in items if it.get("doc")})
    pages = [it.get("page") for it in items if it.get("page")]
    return {
        "documents": len(docs),
        "chunks": len(items),
        "unique_docs": docs,
        "min_page": min(pages) if pages else None,
        "max_page": max(pages) if pages else None,
    }


def build_ui():
    st.set_page_config(page_title="AI Study Mentor — Hackathon Demo", layout="wide")
    inject_css()
    st.markdown("""
    <div class="hero">
      <div>
        <h1>AI Study Mentor</h1>
        <p>RAG + Adaptive Tutoring — polished, fast, demo-ready.</p>
      </div>
      <div class="badges"><span>RAG</span><span>Gemini</span><span>Dark Mode</span></div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar controls and ingest
    with st.sidebar:
        st.header("Settings")
        k = st.slider("Top-k context", 1, 8, 3)
        temperature = st.slider("Temperature", 0.0, 1.0, float(os.getenv("GEMINI_TEMPERATURE", 0.2)), 0.05)

        # Model selection (safe fallback)
        @st.cache_data(ttl=1800)
        def load_models() -> list[str]:
            try:
                client = GeminiClient()
                return client.list_supported_models()
            except Exception:
                return []
        models = load_models()
        model = st.selectbox("Model", options=models or ["gemini-flash-latest"], index=0)

        st.divider()
        st.subheader("Upload & URLs")
        files = st.file_uploader("Upload PDF(s)", type=["pdf"], accept_multiple_files=True)
        urls_text = st.text_area("Paste URLs", placeholder="https://docs.python.org/...\nhttps://github.com/...")
        ingest = st.button("Process Sources")

        if ingest:
            with st.spinner("Processing sources…"):
                try:
                    out_dir = PROJECT_ROOT / "data" / "uploaded_files"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    for f in (files or []):
                        dest = out_dir / f.name
                        dest.write_bytes(f.getbuffer())
                    # Process URLs list for downstream scanners (saved into sources.txt)
                    urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
                    if urls:
                        (out_dir / "sources.txt").write_text("\n".join(urls))
                    # Warm metadata
                    list_chunks_from_dir(str(out_dir.resolve()))
                    toast("Sources processed successfully", "success")
                except Exception as e:
                    st.error(f"Ingest error: {e}")

    # Stats dashboard on top
    engine = RAGEngine(auto_embeddings=False)
    stats = stats_panel(engine)
    c1, c2, c3 = st.columns(3)
    c1.metric("Documents", stats["documents"])
    c2.metric("Chunks", stats["chunks"])
    if "query_count" not in st.session_state:
        st.session_state["query_count"] = 0
    c3.metric("Queries", st.session_state["query_count"])

    # Example questions
    st.caption("Examples: click to auto-fill")
    ex_col = st.columns([1,1,1,1])
    examples = [
        "Explain dynamic programming",
        "Difference between BFS and DFS",
        "What is a monad in functional programming?",
        "How do hash tables handle collisions?",
    ]
    for i, ex in enumerate(examples):
        if ex_col[i].button(ex):
            st.session_state["question"] = ex
            st.experimental_rerun()

    # Visual RAG — side-by-side
    q_col, ctx_col, a_col = st.columns([0.35, 0.30, 0.35])

    with q_col:
        st.subheader("Question")
        question = st.text_area("Enter question", value=st.session_state.get("question",""), height=120)
        run = st.button("Run RAG")
        st.markdown("""
        <div class="pipeline">
          <div class="step">Query</div><div class="arrow">→</div>
          <div class="step">Embed</div><div class="arrow">→</div>
          <div class="step">Search</div><div class="arrow">→</div>
          <div class="step">Retrieve</div><div class="arrow">→</div>
          <div class="step">Generate</div>
        </div>
        """, unsafe_allow_html=True)

    retrieved_chunks: List[Dict[str, Any]] = []
    answer_result: Dict[str, Any] = {}

    if run and question.strip():
        st.session_state["query_count"] += 1
        # Step: retrieve
        with ctx_col:
            st.subheader("Context")
            try:
                chunks = engine.retrieve_context(question, k=k)
                retrieved_chunks = chunks
                st.success(f"Retrieved {len(chunks)} chunk(s)")
                for c in chunks:
                    chunk_card(c, question)
            except Exception as e:
                st.error(f"Retrieval error: {e}")

        # Step: generate (streaming-like)
        with a_col:
            st.subheader("Answer")
            ph = st.empty()
            try:
                result = engine.answer_with_gemini(question, k=k, model=model, temperature=temperature)
                answer_result = result
                full = result.get("answer", "") or ""
                # Simulate streaming word-by-word for UX polish
                accum = []
                for w in full.split():
                    accum.append(w)
                    ph.markdown(" ".join(accum))
                    time.sleep(0.01)
                st.divider()
                st.caption("Sources")
                for c in retrieved_chunks:
                    src = c.get("doc")
                    url = c.get("url") or ""
                    if url:
                        st.markdown(f"- [{src}]({url})")
                    else:
                        st.markdown(f"- {src}")
                toast("Answer generated", "success")
            except Exception as e:
                st.error(f"Generation error: {e}")

        # Chat history
        hist = st.session_state.setdefault("history", [])
        hist.append({"q": question, "answer": answer_result.get("answer", ""), "chunks": retrieved_chunks})

    st.divider()
    st.subheader("Chat History")
    hist = st.session_state.get("history", [])
    if not hist:
        st.info("Ask a question to start the conversation.")
    else:
        for i, h in enumerate(hist[::-1]):
            st.markdown(f"**Q:** {h['q']}")
            st.markdown(h.get("answer", ""))
            with st.expander("Context chunks"):
                for c in h.get("chunks", [])[:3]:
                    chunk_card(c, h["q"])
        # Export
        md = ["# Chat Export\n"]
        for h in hist:
            md.append(f"## Q: {h['q']}\n\n{h.get('answer','')}\n")
        st.download_button("Export markdown", data="\n".join(md), file_name="chat_export.md")


if __name__ == "__main__":
    build_ui()