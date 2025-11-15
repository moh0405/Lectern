import os
import json
import re
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
from backend.advanced_ai import (
    build_concept_map,
    concept_map_to_dot,
    socratic_tutor,
    multi_document_synthesis,
    adaptive_explain,
    math_solve,
)
from frontend.components import inject_assets, command_palette_hint, lottie_animation


def doc_stats(engine: RAGEngine | None = None) -> Dict[str, Any]:
    try:
        if engine is None:
            engine = RAGEngine(auto_embeddings=False)
        items = engine._docstore_iter()
    except Exception:
        # Fallback: scan uploaded sources directly (no FAISS required)
        try:
            from backend.document_processor import list_chunks_from_dir
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
    snippet = (text[:500] + ("…" if len(text) > 500 else ""))
    # Keyword highlights from the last asked question if present
    q = str(st.session_state.get("last_question", ""))
    highlighted = keyword_highlights(q, snippet)
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

def keyword_highlights(question: str, text: str) -> str:
    """Wrap overlapping keywords for visual RAG."""
    try:
        q_tokens = set(re.findall(r"\b\w+\b", (question or "").lower()))
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
        return text


def build_ui() -> None:
    st.set_page_config(page_title="AI Study Mentor — Intelligent Tutor", layout="wide")
    inject_assets()
    # Hero header with badges (polished)
    st.markdown(
        """
        <div class="hero">
          <div>
            <h1>AI Study Mentor</h1>
            <p>RAG + Adaptive Tutoring — polished, fast, demo-ready.</p>
          </div>
          <div class="badges"><span>RAG</span><span>Gemini</span><span>Dark Mode</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
            stats = doc_stats(None)
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

    # Stats dashboard
    stats = doc_stats(None)
    c1, c2, c3 = st.columns(3)
    c1.metric("Documents", stats["documents"])
    c2.metric("Chunks", stats["chunks"])
    if "query_count" not in st.session_state:
        st.session_state["query_count"] = 0
    c3.metric("Queries", st.session_state["query_count"])

    # Main layout: Advanced Tutor Tabs
    tab_ask, tab_map, tab_socratic, tab_synthesis, tab_adaptive, tab_math, tab_viz = st.tabs([
        "Ask",
        "Concept Map",
        "Socratic Tutor",
        "Synthesis",
        "Adaptive Tutor",
        "Math",
        "3D Viz",
    ])

    # Ask tab (RAG Q&A)
    with tab_ask:
        q_col, xr_col = st.columns([0.4, 0.6])
        with q_col:
            st.subheader("Question")
            question = st.text_area("Enter question", placeholder="e.g., What is a linked list?", height=120)
            run = st.button("Run RAG")
            # Pipeline visualization
            st.markdown(
                """
                <div class="pipeline">
                  <div class="step">Query</div><div class="arrow">→</div>
                  <div class="step">Embed</div><div class="arrow">→</div>
                  <div class="step">Search</div><div class="arrow">→</div>
                  <div class="step">Retrieve</div><div class="arrow">→</div>
                  <div class="step">Generate</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with xr_col:
            st.subheader("Context & Answer")
            if run and question.strip():
                st.session_state["last_question"] = question
                st.session_state["query_count"] = st.session_state.get("query_count", 0) + 1

                st.info("Step 1: Retrieving relevant chunks…")
                engine = RAGEngine(auto_embeddings=False)
                chunks = engine.retrieve_context(question, k=k)
                st.success(f"Retrieved {len(chunks)} chunk(s)")

                # Retrieved banner
                st.markdown(f"<div class='retrieved-banner'>Retrieved {len(chunks)} chunk(s)</div>", unsafe_allow_html=True)
                for c in chunks:
                    chunk_card(c)

                st.info("Step 2: Generating answer…")
                mdl = model_input.strip() or None
                result = engine.answer_with_gemini(question, k=k, model=mdl, temperature=temperature)
                prompt = result.get("prompt", "")
                st.session_state["last_prompt"] = prompt
                st.session_state["last_chunks"] = chunks
                st.session_state["last_result"] = result

                # Animated pipeline feedback (subtle)
                lottie_animation({
                    "v":"5.7.4","fr":30,"ip":0,"op":60,"w":600,"h":180,"nm":"bar",
                    "ddd":0,"assets":[],"layers":[{"ddd":0,"ty":4,"nm":"bar","sr":1,
                    "ks":{"o":{"a":0,"k":100},"r":{"a":0,"k":0},"p":{"a":0,"k":[300,90,0]},"a":{"a":0,"k":[0,0,0]},
                    "s":{"a":1,"k":[{"t":0,"s":[10,100,100]},{"t":60,"s":[100,100,100]}]}},
                    "shapes":[{"ty":"rc","d":1,"s":{"a":0,"k":[600,20]},"p":{"a":0,"k":[0,0]},"r":{"a":0,"k":8}},
                    {"ty":"fl","c":{"a":0,"k":[0.486,0.227,0.929,1]},"o":{"a":0,"k":90}}]}] }, width=600, height=180, loop=False)

            # Answer card
            if "last_result" in st.session_state:
                res = st.session_state["last_result"]
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                if res.get("ok"):
                    st.markdown(res.get("answer", ""))
                else:
                    st.error(res.get("error", "Unknown error"))
                st.markdown("</div>", unsafe_allow_html=True)

                # Source attribution list
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

            if show_prompt and (prompt := st.session_state.get("last_prompt")):
                st.subheader("Prompt used")
                st.code(prompt)

    # Concept Map tab
    with tab_map:
        st.subheader("Concept Map Generator")
        topic = st.text_input("Topic", value="Machine Learning")
        gen = st.button("Generate Concept Map")
        if gen:
            result = build_concept_map(topic, temperature=temperature)
            if result.get("ok"):
                nodes = result.get("nodes", [])
                edges = result.get("edges", [])
                dot = concept_map_to_dot(nodes, edges)
                st.graphviz_chart(dot, use_container_width=True)
                # Interactivity: inspect a node
                node_ids = [n.get("id") or n.get("label") for n in nodes]
                selected = st.selectbox("Inspect concept", options=node_ids)
                if selected:
                    # Show neighbors
                    nbrs = []
                    for e in edges:
                        if e.get("from") == selected:
                            nbrs.append((e.get("to"), e.get("label")))
                        elif e.get("to") == selected:
                            nbrs.append((e.get("from"), e.get("label")))
                    st.markdown("**Related concepts:**")
                    for nid, lbl in nbrs:
                        st.markdown(f"- {nid} ({lbl})")
                # Export
                st.download_button("Download JSON", data=json.dumps({"nodes": nodes, "edges": edges}, indent=2), file_name=f"concept-map-{topic}.json")
                st.download_button("Download DOT", data=dot, file_name=f"concept-map-{topic}.dot")
            else:
                st.error(result.get("error", "Could not build map"))

    # Socratic Tutor tab
    with tab_socratic:
        st.subheader("Socratic Tutor Mode")
        q = st.text_area("Your question", placeholder="Ask something you want to reason through.")
        more_help = st.button("Guide me")
        if "socratic_depth" not in st.session_state:
            st.session_state["socratic_depth"] = 0
        if more_help and q.strip():
            # Use RAG context for grounding
            eng = RAGEngine(auto_embeddings=False)
            chunks = eng.retrieve_context(q, k=k)
            out = socratic_tutor(q, chunks, depth=st.session_state["socratic_depth"], temperature=temperature)
            if out.get("ok"):
                st.session_state["socratic_depth"] += 1
                st.markdown("**Guiding Questions**")
                for i, qq in enumerate(out.get("questions", []), 1):
                    st.markdown(f"{i}. {qq}")
                st.markdown("**Hints (progressively explicit)**")
                for i, h in enumerate(out.get("hints", []), 1):
                    st.markdown(f"{i}. {h}")
            else:
                st.error(out.get("error", "Could not generate guidance"))

    # Synthesis tab
    with tab_synthesis:
        st.subheader("Multi-Document Synthesis")
        t = st.text_input("Topic to compare", value="Linked Lists")
        run_syn = st.button("Compare & Synthesize")
        if run_syn:
            res = multi_document_synthesis(t, k_per_doc=2, temperature=temperature)
            if res.get("ok"):
                st.markdown("**Similarities**")
                for s in res.get("similarities", []):
                    st.markdown(f"- {s}")
                st.markdown("**Conflicts**")
                for c in res.get("conflicts", []):
                    st.markdown(f"- {c}")
                st.markdown("**Unified Explanation**")
                st.write(res.get("synthesis", ""))
                st.markdown("**Citations**")
                for cit in res.get("citations", []):
                    st.markdown(f"- {cit.get('doc')}: {cit.get('point')}")
            else:
                st.error(res.get("error", "Could not synthesize"))

    # Adaptive Tutor tab
    with tab_adaptive:
        st.subheader("Explain Like I’m… (Adaptive)")
        level = st.selectbox("Complexity level", options=["ELI5", "ELI10", "Undergrad", "Grad", "Expert"], index=2)
        aq = st.text_area("Question to explain", placeholder="e.g., Explain dynamic programming.")
        run_adapt = st.button("Explain at selected level")
        if run_adapt and aq.strip():
            with st.spinner("Generating adaptive explanation…"):
                try:
                    res = adaptive_explain(aq, level=level, temperature=temperature)
                    if res.get("ok"):
                        st.write(str(res.get("answer", "")))
                        st.divider()
                        st.caption("Context used:")
                        eng = RAGEngine(auto_embeddings=False)
                        for c in res.get("chunks", []):
                            chunk_card(c)
                    else:
                        st.error(res.get("error", "Could not generate explanation"))
                except Exception as e:
                    st.error(f"Adaptive Tutor error: {e}")

    # Math tab
    with tab_math:
        st.subheader("LaTeX Math Rendering + Steps")
        expr = st.text_input("Math prompt", value="differentiate sin(x)")
        run_math = st.button("Compute")
        if run_math and expr.strip():
            with st.spinner("Computing…"):
                try:
                    res = math_solve(expr)
                    if res.get("ok"):
                        if res.get("latex"):
                            st.latex(res.get("latex"))
                        st.markdown("**Steps**")
                        for s in res.get("steps", []):
                            st.markdown(f"- {s}")
                    else:
                        err = res.get("error", "Math engine error")
                        st.error(err)
                        if "sympy" in err.lower():
                            st.info("Tip: install `sympy` for full math features: `pip install sympy`. ")
                except Exception as e:
                    st.error(f"Math error: {e}")

    # 3D Embedding Visualization tab
    with tab_viz:
        st.subheader("Embedding Space (3D)")
        st.caption("Rotate, zoom, click points to inspect chunk text.")
        try:
            import numpy as np
            try:
                import plotly.express as px
            except Exception:
                px = None
            items = RAGEngine(auto_embeddings=False)._docstore_iter()
            # Sample to keep the viz lightweight
            max_points = st.slider("Max points", 50, 500, 200)
            items = items[:max_points]
            texts = [it.get("text","") for it in items]
            labels = [it.get("doc","") for it in items]
            # Safe, deterministic pseudo-embeddings (no SentenceTransformer to avoid segfaults)
            import hashlib
            vecs = []
            for t in texts:
                h = hashlib.sha256(t.encode('utf-8')).digest()
                vecs.append(np.frombuffer(h[:96], dtype=np.uint8).astype(np.float32))
            mat = np.stack(vecs, axis=0) if vecs else np.zeros((0,96), dtype=np.float32)
            # Dimensionality reduction
            try:
                from sklearn.manifold import TSNE
                # Ensure perplexity is valid (< n_samples)
                n = max(1, len(texts))
                perplex = max(2, min(30, n - 1))
                pts = TSNE(n_components=3, init='pca', perplexity=perplex, learning_rate='auto').fit_transform(mat)
            except Exception:
                # PCA fallback
                if mat.shape[0] and mat.shape[1] >= 3:
                    U, S, Vt = np.linalg.svd(mat - mat.mean(0), full_matrices=False)
                    pts = (mat - mat.mean(0)) @ Vt[:3].T
                else:
                    pts = np.zeros((len(texts), 3))
            if px is None:
                st.warning("Plotly not installed; install plotly to enable interactive 3D scatter.")
            else:
                import pandas as pd
                df = pd.DataFrame({"x": pts[:,0], "y": pts[:,1], "z": pts[:,2], "label": labels, "text": [t[:160] for t in texts]})
                fig = px.scatter_3d(df, x="x", y="y", z="z", color="label", hover_name="label", hover_data={"text": True})
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"3D visualization error: {e}")

    # Global keyboard shortcut hints
    command_palette_hint()


if __name__ == "__main__":
    build_ui()