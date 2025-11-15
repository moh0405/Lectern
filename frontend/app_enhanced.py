import os
from typing import List, Dict, Any
import sys
from pathlib import Path

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Ensure project root is on the Python path so `backend` is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.rag_engine import RAGEngine
from backend.llm_config import GeminiClient
from backend.document_processor import list_chunks_from_dir


def doc_stats(engine: RAGEngine) -> Dict[str, Any]:
    items = engine._docstore_iter()
    docs = sorted({it.get("doc", "") for it in items if it.get("doc")})
    pages = [it.get("page") for it in items if it.get("page")]
    return {
        "documents": len(docs),
        "chunks": len(items),
        "unique_docs": docs,
        "min_page": min(pages) if pages else None,
        "max_page": max(pages) if pages else None,
    }


def relevance_color(score: float) -> str:
    if score is None:
        return "#cccccc"
    if score >= 0.6:
        return "#22c55e"  # green
    if score >= 0.3:
        return "#f59e0b"  # amber
    return "#ef4444"  # red


def chunk_card(chunk: Dict[str, Any]) -> None:
    score = float(chunk.get("score") or 0.0)
    color = relevance_color(score)
    doc = chunk.get("doc", "")
    page = chunk.get("page", None)
    text = (chunk.get("text", "") or "").strip()
    snippet = (text[:400] + ("…" if len(text) > 400 else ""))
    st.markdown(
        f"""
        <div style="border-left: 6px solid {color}; padding: 10px; margin-bottom: 10px; background: #0f172a18;">
            <div style="font-size: 0.9rem; color: #64748b;">Source: <strong>{doc}</strong>{f' — page {page}' if page else ''}</div>
            <div style="font-size: 0.85rem; color: #334155;">Similarity: <strong>{score:.4f}</strong></div>
            <div style="margin-top: 6px;">{snippet}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_ui() -> None:
    st.set_page_config(page_title="AI Study Mentor — RAG Visualizer", layout="wide")
    st.title("AI Study Mentor — RAG Visualizer (Gemini Cloud)")
    st.caption("Explore how RAG selects context and forms answers, visually.")

    # Sidebar settings
    with st.sidebar:
        st.header("Settings")
        k = st.slider("Top-k context chunks", min_value=1, max_value=8, value=3, step=1)
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=float(os.getenv("GEMINI_TEMPERATURE", 0.2)), step=0.05)
        # Load available models and present a dropdown of supported ones
        @st.cache_data(ttl=3600)
        def load_models() -> list[str]:
            try:
                client = GeminiClient()
                return client.list_supported_models()
            except Exception:
                return []

        models = load_models()
        default_model_env = os.getenv("GEMINI_MODEL", "")
        default_idx = 0
        if models:
            # Prefer non-1.5 alias for broader availability
            if "gemini-flash-latest" in models:
                default_idx = models.index("gemini-flash-latest")
            elif "gemini-1.5-flash-latest" in models:
                default_idx = models.index("gemini-1.5-flash-latest")
            elif default_model_env in models:
                default_idx = models.index(default_model_env)
            model_input = st.selectbox("Model", options=models, index=default_idx, help="Only shows models that support generateContent")
            with st.expander("Available models", expanded=False):
                st.write(models)
        else:
            st.warning("Could not list models for your API key. Enter a model manually or set GEMINI_MODEL in .env.")
            fallback_default = default_model_env or "gemini-1.0-pro"
            model_input = st.text_input("Model (optional)", value=fallback_default)
        show_prompt = st.checkbox("Show final prompt", value=False)
        st.divider()
        st.subheader("Document Stats")
        try:
            engine_tmp = RAGEngine(auto_embeddings=False)
            stats = doc_stats(engine_tmp)
            st.markdown(f"- Documents: {stats['documents']}")
            st.markdown(f"- Chunks: {stats['chunks']}")
            if stats["min_page"] is not None:
                st.markdown(f"- Page range: {stats['min_page']}–{stats['max_page']}")
            if stats["unique_docs"]:
                st.markdown("- Sources:")
                for d in stats["unique_docs"]:
                    st.markdown(f"  - {d}")
        except Exception as e:
            st.warning(f"Stats unavailable: {e}")

        st.divider()
        st.subheader("Add Sources")
        with st.expander("Add URLs (one per line)", expanded=False):
            st.caption("YouTube, web article, or GitHub repo")
            existing = ""
            try:
                sources_fp = Path("data/uploaded_files/sources.txt")
                if sources_fp.exists():
                    existing = sources_fp.read_text()
            except Exception:
                pass
            urls_text = st.text_area("sources.txt", value=existing, height=120)
            if st.button("Save URLs"):
                try:
                    sources_fp = Path("data/uploaded_files/sources.txt")
                    sources_fp.parent.mkdir(parents=True, exist_ok=True)
                    sources_fp.write_text(urls_text.strip())
                    st.success("Saved sources.txt. Use 'Refresh stats' to rescan.")
                except Exception as e:
                    st.error(f"Could not save: {e}")

        with st.expander("Upload audio (mp3/mp4/wav/m4a)", expanded=False):
            up = st.file_uploader("Audio file", type=["mp3","mp4","wav","m4a"], accept_multiple_files=False)
            if up is not None:
                try:
                    out_fp = Path("data/uploaded_files") / up.name
                    out_fp.parent.mkdir(parents=True, exist_ok=True)
                    out_fp.write_bytes(up.getbuffer())
                    st.success(f"Uploaded {up.name}. Use 'Refresh stats' to rescan.")
                except Exception as e:
                    st.error(f"Upload failed: {e}")

        if st.button("Refresh stats"):
            try:
                # Warm metadata by scanning sources so stats update immediately
                list_chunks_from_dir(str(Path("data/uploaded_files").resolve()))
                st.experimental_rerun()
            except Exception:
                st.experimental_rerun()

    # Main layout
    col_left, col_right = st.columns([0.5, 0.5])

    with col_left:
        st.subheader("Ask a question")
        question = st.text_area("Question", placeholder="e.g., What is a linked list?", height=100)
        run = st.button("Run RAG")

        if run and question.strip():
            st.info("Step 1: Retrieving relevant chunks…")
            engine = RAGEngine(auto_embeddings=False)
            chunks = engine.retrieve_context(question, k=k)
            st.success(f"Retrieved {len(chunks)} chunk(s)")

            st.subheader("Selected Context")
            for c in chunks:
                chunk_card(c)

            st.info("Step 2: Generating answer with Gemini (cloud)…")
            mdl = model_input.strip() or None
            result = engine.answer_with_gemini(question, k=k, model=mdl, temperature=temperature)
            prompt = result.get("prompt", "")
            st.session_state["last_prompt"] = prompt
            st.session_state["last_chunks"] = chunks

            if show_prompt:
                st.subheader("Prompt used")
                st.code(prompt)

            st.session_state["last_result"] = result

    with col_right:
        st.subheader("Answer")
        if "last_result" in st.session_state:
            res = st.session_state["last_result"]
            if res.get("ok"):
                st.markdown(res.get("answer", ""))
                # Source attribution
                st.divider()
                st.caption("Sources")
                for c in st.session_state.get("last_chunks", []):
                    src_type = c.get("source") or "pdf"
                    doc = c.get("doc", "")
                    page = c.get("page")
                    url = c.get("url")
                    start = c.get("start")
                    end = c.get("end")
                    extra = []
                    if page:
                        extra.append(f"page {page}")
                    if src_type in ("youtube", "audio") and (start is not None):
                        try:
                            def fmt(t: float) -> str:
                                t = int(t)
                                return f"{t//60}:{t%60:02d}"
                            extra.append(f"{fmt(float(start))}–{fmt(float(end or start))}")
                        except Exception:
                            pass
                    if url:
                        extra.append(url)
                    label = doc or (url or src_type)
                    suffix = f" ({'; '.join(extra)})" if extra else ""
                    st.markdown(f"- {label}{suffix}")
            else:
                st.error(res.get("error", "Unknown error"))


if __name__ == "__main__":
    build_ui()