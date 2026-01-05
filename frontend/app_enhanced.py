import os
import json
import re
import time
from typing import List, Dict, Any
import sys
from pathlib import Path

import streamlit as st

# Must be the first Streamlit command in this script
st.set_page_config(page_title="AI Study Mentor — Intelligent Tutor", layout="wide")

# Global visual polish (animated gradient, glassmorphism, glowing metrics, tabs, inputs)
st.markdown(
    """
    <style>
      /* Animated gradient background */
      .stApp {
        background: linear-gradient(-45deg, #1a1a2e, #16213e, #0f3460, #1a1a2e);
        background-size: 400% 400%;
        animation: gradient 15s ease infinite;
      }
      @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
      }

      /* Subtle glass surfaces (responsive-safe) */
      [data-testid="stMetric"], [data-testid="stExpander"], .stAlert {
        background: rgba(255, 255, 255, 0.04) !important;
        backdrop-filter: blur(6px) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25) !important;
      }
      .block-container {
        max-width: 1200px;
        padding-left: 1rem;
        padding-right: 1rem;
      }

      /* Glowing stats */
      [data-testid="stMetricValue"] {
        font-size: clamp(1.5rem, 3.2vw, 2.6rem) !important;
        font-weight: 800 !important;
        background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        text-shadow: 0 0 30px rgba(102, 126, 234, 0.5);
        animation: glow 2s ease-in-out infinite;
      }
      @keyframes glow {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.8; }
      }

      /* Buttons */
      .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
        border-radius: 25px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        color: white !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
        transition: all 0.3s ease !important;
      }
      .stButton > button:hover {
        transform: translateY(-2px) scale(1.03) !important;
        box-shadow: 0 6px 22px rgba(102, 126, 234, 0.55) !important;
      }

      /* Tabs */
      .stTabs [data-baseweb="tab-list"] { gap: 8px; }
      .stTabs [data-baseweb="tab"] {
        border-radius: 15px;
        padding: 12px 24px;
        background: rgba(255, 255, 255, 0.05);
        transition: all 0.3s ease;
      }
      .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        box-shadow: 0 0 20px rgba(102, 126, 234, 0.6);
      }

      /* Inputs */
      .stTextArea textarea, .stTextInput input {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 2px solid rgba(102, 126, 234, 0.3) !important;
        border-radius: 15px !important;
        color: white !important;
        padding: 1rem !important;
        transition: all 0.3s ease !important;
      }
      .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 20px rgba(102, 126, 234, 0.4) !important;
      }

      /* Example question buttons (pill style) */
      div[data-testid="column"] .stButton > button {
        border-radius: 50px !important;
        padding: 0.5rem 1.5rem !important;
        font-size: 0.9rem !important;
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(102, 126, 234, 0.3) !important;
      }

      /* Pipeline visualization */
      .pipeline-step {
        display: inline-block;
        padding: 8px 16px;
        background: rgba(102, 126, 234, 0.2);
        border-radius: 20px;
        margin: 0 5px;
        animation: pulse 2s ease-in-out infinite;
      }
      @keyframes pulse {
        0%, 100% { opacity: 0.6; }
        50% { opacity: 1; }
      }

      /* Header title gradient */
      h1 {
        font-size: 3.5rem !important;
        font-weight: 900 !important;
        background: linear-gradient(90deg, #667eea, #764ba2, #f093fb, #667eea);
        background-size: 200% auto;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        animation: shine 3s linear infinite;
      }
      @keyframes shine { to { background-position: 200% center; } }

      /* Context cards */
      .context-card {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
        border-left: 4px solid #667eea;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        backdrop-filter: blur(5px);
        transition: all 0.3s ease;
      }
      .context-card:hover {
        transform: translateX(5px);
        box-shadow: 0 5px 20px rgba(102, 126, 234, 0.3);
      }

      /* Loading spinner */
      .stSpinner > div {
        border-color: #667eea transparent transparent transparent !important;
        animation: spin 1s linear infinite;
      }
      @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

      /* Sidebar styling */
      [data-testid="stSidebar"] {
        background: rgba(0, 0, 0, 0.3) !important;
        backdrop-filter: blur(10px) !important;
      }

      /* Reduced motion preference */
      @media (prefers-reduced-motion: reduce) {
        .stApp { animation: none !important; }
        .stButton > button, .stTabs [data-baseweb="tab"] { transition: none !important; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

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
try:
    from frontend.demo_module import render_demo_app
except Exception:
    render_demo_app = None
from backend.leetcode_handler import LeetCodeHandler
import random
import functools


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


@st.cache_data(ttl=600)
def doc_stats_cached() -> Dict[str, Any]:
    """Cached wrapper to avoid repeated scans during startup and sidebar refreshes."""
    return doc_stats(None)


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


def init_analytics():
    # Initialize session analytics before any UI logic uses it
    if "analytics" not in st.session_state:
        st.session_state["analytics"] = {
            "session_start": time.time(),
            "events": [],  # each: {ts, q, avg_sim, latency_ms, tokens_prompt, tokens_answer, docs, cache_hit}
            "doc_usage": {},  # doc -> count
            "streak_days": 0,
            # parallel arrays for simple charts
            "queries": [],
            "timestamps": [],
            "scores": [],
            "sources": [],
        }
    if "query_cache" not in st.session_state:
        st.session_state["query_cache"] = {}


# -----------------------------------------------------
# Performance: cached resources and data-level caches
# -----------------------------------------------------
@st.cache_resource
def load_rag_engine(version: int = 2) -> RAGEngine:
    """Load once and keep in memory; prefer precomputed embeddings if available.

    If `data/vector_store/embeddings.npy` exists, enable `auto_embeddings` so the engine
    loads them without importing heavy libraries. Otherwise, avoid auto-embedding to
    prevent startup crashes on environments where `sentence-transformers` or `torch`
    are unavailable.
    """
    try:
        emb_path = Path("data/vector_store/embeddings.npy").resolve()
        auto = emb_path.exists()
    except Exception:
        auto = False
    try:
        return RAGEngine(auto_embeddings=auto)
    except Exception:
        # Fallback to meta-only; retrieval will use keyword overlap
        return RAGEngine(auto_embeddings=False)


@st.cache_resource
def load_leetcode_handler() -> LeetCodeHandler:
    return LeetCodeHandler()


rag_engine = load_rag_engine(version=2)


@st.cache_data(ttl=300)
def search_cached(query: str, k: int = 3) -> List[Dict[str, Any]]:
    return rag_engine.retrieve_context(query, k)


@st.cache_data(ttl=3600)
def get_answer_cached(question: str, k: int, model: str | None, temperature: float, context_text: str | None = None) -> Dict[str, Any]:
    # If explicit context provided, synthesize directly; else perform retrieval-driven answer
    if context_text:
        try:
            # Prefer direct synthesis on provided context
            return rag_engine.generate_answer(question, context_text, model=model, temperature=temperature, mode="technical")
        except AttributeError:
            # Fallback if engine instance predates patch: do standard retrieval answer
            return rag_engine.answer_with_gemini(question, k=k, model=model, temperature=temperature)
    return rag_engine.answer_with_gemini(question, k=k, model=model, temperature=temperature)


def record_event(question: str, chunks: List[Dict[str, Any]], result: Dict[str, Any], latency_ms: int, cache_hit: bool = False):
    # Safely record a query interaction for analytics and streaks
    try:
        sims = [float(c.get("score") or 0.0) for c in (chunks or [])]
        avg_sim = sum(sims)/len(sims) if sims else 0.0
        prompt = result.get("prompt", "")
        answer = result.get("answer", "")
        tokens_prompt = int(len(prompt)/4)
        tokens_answer = int(len(answer)/4)
        docs = [c.get("doc") or (c.get("url") or "") for c in (chunks or [])]
        ev = {
            "ts": time.time(),
            "q": question,
            "avg_sim": avg_sim,
            "latency_ms": latency_ms,
            "tokens_prompt": tokens_prompt,
            "tokens_answer": tokens_answer,
            "docs": docs,
            "cache_hit": bool(cache_hit),
        }
        st.session_state["analytics"]["events"].append(ev)
        # parallel arrays for Analytics tab
        st.session_state["analytics"]["queries"].append(question)
        st.session_state["analytics"]["timestamps"].append(time.time())
        st.session_state["analytics"]["scores"].append(avg_sim)
        st.session_state["analytics"]["sources"].append(docs)
        # doc usage
        du = st.session_state["analytics"]["doc_usage"]
        for d in docs:
            if not d:
                continue
            du[d] = du.get(d, 0) + 1
        # streak: if last event day differs from previous and is consecutive
        evs = st.session_state["analytics"]["events"]
        if len(evs) >= 2:
            import datetime as _dt
            prev_day = _dt.datetime.fromtimestamp(evs[-2]["ts"]).date()
            curr_day = _dt.datetime.fromtimestamp(evs[-1]["ts"]).date()
            if (curr_day - prev_day).days == 1:
                st.session_state["analytics"]["streak_days"] += 1
            elif (curr_day - prev_day).days > 1:
                st.session_state["analytics"]["streak_days"] = 1
        else:
            st.session_state["analytics"]["streak_days"] = 1
    except Exception:
        pass


def build_ui() -> None:
    inject_assets()
    init_analytics()
    # One-time prewarm for retrieval cache to ensure sub-2s first response
    if "__prewarmed__" not in st.session_state:
        try:
            for _q in [
                "Explain dynamic programming",
                "What is a hash table?",
                "Difference between BFS and DFS",
                "Describe Dijkstra vs Bellman-Ford",
            ]:
                _ = search_cached(_q, k=3)
        except Exception:
            pass
        st.session_state["__prewarmed__"] = True
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
    demo_mode_active = False
    with st.sidebar:
        demo_mode = st.checkbox("Demo Mode", value=False, help="Switch to instant, cached demo experience")
        if demo_mode and render_demo_app:
            st.success("Demo Mode active — instant responses and mock analytics")
            if st.button("Switch back to Normal Mode"):
                st.session_state["__force_normal__"] = True
            else:
                demo_mode_active = True
        st.header("Settings")
        k = st.slider("Top-k context chunks", min_value=1, max_value=8, value=3, step=1)
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=float(os.getenv("GEMINI_TEMPERATURE", 0.2)), step=0.05)
        # Defer model listing until explicitly requested to avoid slow startup
        default_model_env = os.getenv("GEMINI_MODEL", "")
        fallback_default = default_model_env or "gemini-flash-latest"
        if st.checkbox("Load supported models from API", value=False, help="Query API to list available models"):
            @st.cache_data(ttl=1800)
            def load_models() -> list[str]:
                try:
                    client = GeminiClient()
                    return client.list_supported_models()
                except Exception:
                    return []
            models = load_models()
            if models:
                default_idx = 0
                if "gemini-flash-latest" in models:
                    default_idx = models.index("gemini-flash-latest")
                elif default_model_env in models:
                    default_idx = models.index(default_model_env)
                model_input = st.selectbox("Model", options=models, index=default_idx, help="Models supporting text generation")
                with st.expander("Available models", expanded=False):
                    st.write(models)
            else:
                st.warning("No models returned; using manual input.")
                model_input = st.text_input("Model (optional)", value=fallback_default)
        else:
            model_input = st.text_input("Model (optional)", value=fallback_default)
        generate_answers = st.checkbox("Generate answers (Gemini)", value=True, help="Disable for instant retrieval-only mode")
        show_prompt = st.checkbox("Show final prompt", value=False)
        st.divider()
        st.subheader("Document Stats")
        try:
            stats = doc_stats_cached()
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

        # Demo Warm-Up: prefill retrieval and answer caches for instant interactions
        st.divider()
        if st.button("Demo Warm-Up", help="Preload caches for popular queries to ensure instant responses"):
            warm_questions = [
                "Explain dynamic programming",
                "What is a hash table?",
                "Difference between BFS and DFS",
                "Describe Dijkstra vs Bellman-Ford",
                "What is a linked list?",
            ]
            with st.spinner("Warming caches…"):
                start_ts = time.time()
                warmed = 0
                for wq in warm_questions:
                    try:
                        chunks = search_cached(wq, k=3)
                        # Optionally warm answer cache if generation is enabled
                        if generate_answers:
                            mdl = (model_input or "").strip() or None
                            result = get_answer_cached(wq, k=3, model=mdl, temperature=temperature)
                        else:
                            # Populate manual cache with retrieval-only result
                            result = {"ok": True, "answer": "Generation disabled (Fast Mode).", "prompt": rag_engine.generate_prompt(wq, chunks)}
                        # Populate manual per-session cache to show cache hits in UI
                        try:
                            st.session_state["query_cache"][wq] = {"chunks": chunks, "result": result}
                        except Exception:
                            pass
                        warmed += 1
                    except Exception:
                        continue
                dur_ms = int((time.time() - start_ts) * 1000)
                st.success(f"Warmed {warmed} queries in {dur_ms} ms ✓")

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

    # If Demo Mode is active, render in main content and exit early
    if demo_mode_active and (render_demo_app is not None):
        render_demo_app()
        return

    # Stats dashboard
    stats = doc_stats(None)
    c1, c2, c3 = st.columns(3)
    c1.metric("Documents", stats["documents"])
    c2.metric("Chunks", stats["chunks"])
    if "query_count" not in st.session_state:
        st.session_state["query_count"] = 0
    c3.metric("Queries", st.session_state["query_count"])

    # Main layout: Advanced Tutor Tabs
    tab_ask, tab_map, tab_socratic, tab_synthesis, tab_adaptive, tab_math, tab_viz, tab_leetcode, tab_analytics = st.tabs([
        "Ask",
        "Concept Map",
        "Socratic Tutor",
        "Synthesis",
        "Adaptive Tutor",
        "Math",
        "3D Viz",
        "LeetCode",
        "Analytics",
    ])

    # Ask tab (RAG Q&A)
    with tab_ask:
        q_col, xr_col = st.columns([0.4, 0.6])
        with q_col:
            st.subheader("Question")
            # Example questions and shortcuts
            st.markdown("**Try these:**")
            ex_cols = st.columns(4)
            if ex_cols[0].button("Explain DP"):
                st.session_state["question"] = "Explain dynamic programming"
            if ex_cols[1].button("Hash Tables"):
                st.session_state["question"] = "What is a hash table?"
            if ex_cols[2].button("BFS vs DFS"):
                st.session_state["question"] = "Difference between BFS and DFS"
            if ex_cols[3].button("Solve Two Sum"):
                st.session_state["question"] = "Solve Two Sum problem"

            with st.form("ask-form"):
                question = st.text_area("Enter question", value=st.session_state.get("question",""), placeholder="e.g., What is a linked list?", height=120)
                submitted = st.form_submit_button("Run RAG")
            st.caption("Shortcuts: Enter (submit), Cmd+K (search)")
            run = submitted
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

                start_ts = time.time()
                cache_hit = False
                # Simple cache to demonstrate cache hit rate
                msgs = ["Searching ~12k chunks… (≈1s)", "Index hit — fetching top-k", "Computing similarities…"]
                holder = st.empty()
                if question in st.session_state["query_cache"]:
                    cached = st.session_state["query_cache"][question]
                    chunks = cached.get("chunks", [])
                    result = cached.get("result", {})
                    cache_hit = True
                else:
                    with st.spinner("Searching vector store…"):
                        holder.info(random.choice(msgs))
                        chunks = search_cached(question, k=k)
                    st.success(f"Found {len(chunks)} relevant chunk(s) ✓")

                # Retrieved banner (do not render raw chunks inline)
                st.markdown(f"<div class='retrieved-banner'>Retrieved {len(chunks)} chunk(s)</div>", unsafe_allow_html=True)

                if not cache_hit and generate_answers:
                    holder.info("Generating synthesized answer (cached for 60 min)…")
                    mdl = model_input.strip() or None
                    # Build explicit context text for higher-quality synthesis
                    context_text = "\n\n---\n\n".join([
                        f"From {c.get('doc','')}" + (f" (page {c.get('page')})" if c.get('page') else "") + ":\n" + (c.get('text','') or "")
                        for c in chunks
                    ])
                    result = get_answer_cached(question, k=k, model=mdl, temperature=temperature, context_text=context_text)
                elif not cache_hit and not generate_answers:
                    # Provide a quick summary from context instead of raw chunks
                    summary_prompt = rag_engine.generate_prompt(question, chunks, mode="summary")
                    result = {"ok": True, "answer": summary_prompt, "prompt": summary_prompt}
                prompt = result.get("prompt", "")
                st.session_state["last_prompt"] = prompt
                st.session_state["last_chunks"] = chunks
                st.session_state["last_result"] = result
                latency_ms = int((time.time() - start_ts) * 1000)
                record_event(question, chunks, result, latency_ms, cache_hit=cache_hit)
                if not cache_hit:
                    st.session_state["query_cache"][question] = {"chunks": chunks, "result": result}

                # Animated pipeline feedback (subtle)
                lottie_animation({
                    "v":"5.7.4","fr":30,"ip":0,"op":60,"w":600,"h":180,"nm":"bar",
                    "ddd":0,"assets":[],"layers":[{"ddd":0,"ty":4,"nm":"bar","sr":1,
                    "ks":{"o":{"a":0,"k":100},"r":{"a":0,"k":0},"p":{"a":0,"k":[300,90,0]},"a":{"a":0,"k":[0,0,0]},
                    "s":{"a":1,"k":[{"t":0,"s":[10,100,100]},{"t":60,"s":[100,100,100]}]}},
                    "shapes":[{"ty":"rc","d":1,"s":{"a":0,"k":[600,20]},"p":{"a":0,"k":[0,0]},"r":{"a":0,"k":8}},
                    {"ty":"fl","c":{"a":0,"k":[0.486,0.227,0.929,1]},"o":{"a":0,"k":90}}]}] }, width=600, height=180, loop=False)

            # Answer card — ONE coherent answer
            if "last_result" in st.session_state:
                res = st.session_state["last_result"]
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                if res.get("ok"):
                    st.markdown("### Answer")
                    st.markdown(res.get("answer", ""))
                else:
                    st.error(res.get("error", "Unknown error"))
                st.markdown("</div>", unsafe_allow_html=True)
                # Sources and raw chunks are hidden under an expander
                with st.expander("📚 View Retrieved Context"):
                    for i, c in enumerate(st.session_state.get("last_chunks", []), 1):
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
                        parts = [str(p) for p in extra if p is not None and str(p) != ""]
                        suffix = f" ({'; '.join(parts)})" if parts else ""
                        st.info(f"**Source {i}** — {doc}{suffix}")
                        snippet = (c.get("text") or "")[:500]
                        if snippet:
                            st.code(snippet + ("..." if len(c.get("text") or "") > 500 else ""))
                        extra.append(url)
                    label = doc or (url or src_type)
                    parts2 = [str(p) for p in extra if p is not None and str(p) != ""]
                    suffix = f" ({'; '.join(parts2)})" if parts2 else ""
                    st.markdown(f"- {label}{suffix}")

            if show_prompt and (prompt := st.session_state.get("last_prompt")):
                st.subheader("Prompt used")
                st.code(prompt)

    # Analytics dashboard
    with tab_analytics:
        st.subheader("Analytics Dashboard")
        evs = st.session_state["analytics"]["events"]
        if not evs:
            st.info("Run a few queries to populate analytics.")
        else:
            try:
                import plotly.express as px
                import plotly.graph_objects as go
                import pandas as pd
                df = pd.DataFrame(evs)
                # Top Metrics
                tm1, tm2, tm3, tm4 = st.columns(4)
                total_queries = len(df)
                avg_similarity = float(df["avg_sim"].mean()) if "avg_sim" in df else 0.0
                topics_covered = len(set([t for q in df["q"].tolist() for t in re.findall(r"\b\w+\b", str(q).lower()) if len(t)>2]))
                streak_days = st.session_state["analytics"].get("streak_days", 1)
                tm1.metric("Total Queries", total_queries)
                tm2.metric("Avg Similarity", f"{avg_similarity:.2f}")
                tm3.metric("Topics Covered", topics_covered)
                tm4.metric("Study Streak", f"{streak_days} days")

                # Query Timeline
                df_time = df.copy()
                df_time["time"] = df_time["ts"].apply(lambda t: time.strftime('%H:%M:%S', time.localtime(t)))
                fig_tl = px.line(df_time, x="time", y=df_time.index, labels={"y":"Queries"}, title="Query Timeline")
                st.plotly_chart(fig_tl, use_container_width=True)

                # Topic Distribution (bar)
                tokens = {}
                for q in df["q"].tolist():
                    for t in re.findall(r"\b\w+\b", str(q).lower()):
                        if len(t) <= 2:
                            continue
                        tokens[t] = tokens.get(t, 0) + 1
                df_topics = pd.DataFrame({"topic": list(tokens.keys()), "count": list(tokens.values())}).sort_values("count", ascending=False).head(20)
                fig_topics = px.bar(df_topics, x="topic", y="count", title="Most Queried Topics")
                st.plotly_chart(fig_topics, use_container_width=True)

                # Similarity Gauge
                gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=max(0.0, min(1.0, avg_similarity)) * 100,
                    title={"text": "Average Similarity (%)"},
                    gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#22c55e"}},
                ))
                st.plotly_chart(gauge, use_container_width=True)

                # Document Usage Heatmap
                du = st.session_state["analytics"]["doc_usage"]
                if du:
                    df_du = pd.DataFrame({"doc": list(du.keys()), "count": list(du.values())})
                    fig_heat = px.imshow(df_du[["count"]].values.reshape(-1, 1),
                                         labels=dict(x="Count", y="Document"),
                                         x=["Queries"], y=df_du["doc"].tolist(),
                                         title="Document Usage (Heatmap)")
                    st.plotly_chart(fig_heat, use_container_width=True)
                else:
                    st.info("No document usage yet.")

                # Export Options
                st.markdown("**Export**")
                report_md = "\n".join([f"- {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e['ts']))}: Q='{e['q']}', sim={e['avg_sim']:.2f}, lat={e['latency_ms']}ms" for e in evs])
                st.download_button("Download Study Report (Markdown)", data=report_md, file_name="study-report.md")
                import csv
                from io import StringIO
                sio = StringIO()
                writer = csv.DictWriter(sio, fieldnames=["ts","q","avg_sim","latency_ms","tokens_prompt","tokens_answer","cache_hit"]) 
                writer.writeheader()
                for e in evs:
                    writer.writerow({k: e.get(k) for k in writer.fieldnames})
                st.download_button("Export Analytics (CSV)", data=sio.getvalue(), file_name="analytics.csv")

            except Exception as e:
                st.error(f"Analytics rendering error: {e}")

    # LeetCode tab
    with tab_leetcode:
        st.subheader("LeetCode Practice + Mentor")
        # Lazy init and cache heavy datasets
        if "leetcode_loaded" not in st.session_state:
            if st.button("Load LeetCode data"):
                with st.spinner("Loading LeetCode data… (one-time)"):
                    st.session_state["leetcode"] = load_leetcode_handler()
                    st.session_state["leetcode_loaded"] = True
        if st.session_state.get("leetcode_loaded"):
            lc: LeetCodeHandler = st.session_state["leetcode"]
        else:
            st.info("Click 'Load LeetCode data' to enable search.")
            lc = None

        c1, c2 = st.columns([1, 2])
        if lc:
            if c1.button("Refresh Datasets"):
                with st.spinner("Refreshing LeetCode datasets…"):
                    try:
                        n, status = lc.load_all(generate_embeddings=False)
                        st.success(f"Loaded {n} problems ({status})")
                    except Exception as e:
                        st.error(f"LeetCode load failed: {e}")
        if lc and lc.is_loaded():
            stats = lc.get_stats()
            c2.metric("Problems", stats.get("total", 0))
            by_diff = stats.get("by_difficulty", {})
            d1, d2, d3 = st.columns(3)
            d1.metric("Easy", by_diff.get("Easy", 0))
            d2.metric("Medium", by_diff.get("Medium", 0))
            d3.metric("Hard", by_diff.get("Hard", 0))

        st.divider()
        query = st.text_input("Search problems", value="binary tree traversal", disabled=lc is None)
        left, right = st.columns([1, 2])
        difficulties = left.multiselect("Difficulty", options=["Easy", "Medium", "Hard"], default=["Easy", "Medium", "Hard"]) 
        topic_str = left.text_input("Topics (comma-separated)", value="Tree, DFS, BFS")
        topics = [t.strip() for t in topic_str.split(",") if t.strip()]
        top_k = right.slider("Top K", min_value=5, max_value=30, value=10)
        run = right.button("Search", disabled=lc is None)

        results = []
        if run and lc is not None:
            with st.spinner("Searching…"):
                try:
                    results = lc.search(query, top_k=top_k, difficulty=difficulties, topics=topics)
                except Exception as e:
                    st.error(f"Search failed: {e}")

        if results:
            st.caption(f"Showing {len(results)} matches")
            for r in results:
                with st.expander(f"{r['title']} [{r['difficulty']}] — score {r['score']:.3f}"):
                    meta_cols = st.columns(4)
                    meta_cols[0].write(f"PID: {r['pid']}")
                    meta_cols[1].write(f"Likes: {r.get('likes') or '-'}")
                    meta_cols[2].write(f"Acceptance: {r.get('acceptance') or '-'}")
                    if r.get("url"):
                        meta_cols[3].write(f"[Open]({r['url']})")

                    exp_c1, exp_c2 = st.columns([1, 1])
                    if exp_c1.button("Explain & Guide", key=f"exp_{r['pid']}"):
                        with st.spinner("Generating study guide…"):
                            try:
                                mdl = (model_input or "").strip() or None
                                out = lc.explain_problem(r["pid"], temperature=temperature, model=mdl)
                                if out.get("ok"):
                                    st.markdown(out.get("markdown") or "")
                                else:
                                    st.error(out.get("error"))
                            except Exception as e:
                                st.error(f"Explanation failed: {e}")

                    # Track analytics for LeetCode searches
                    try:
                        st.session_state["analytics"]["events"].append({
                            "ts": time.time(),
                            "q": f"LeetCode search: {query}",
                            "avg_sim": float(r.get("score", 0.0)),
                            "latency_ms": 0,
                            "tokens_prompt": None,
                            "tokens_answer": None,
                        })
                    except Exception:
                        pass

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
            # Load chunk metadata; if engine docstore is empty, fall back to direct scan
            items = RAGEngine(auto_embeddings=False)._docstore_iter()
            if not items:
                try:
                    from backend.document_processor import list_chunks_from_dir
                    items = list_chunks_from_dir(str(Path("data/uploaded_files").resolve()))
                except Exception:
                    items = []
            # Sample to keep the viz lightweight
            max_points = st.slider("Max points", 50, 500, 200)
            items = items[:max_points]
            texts = [it.get("text","") for it in items]
            labels = [it.get("doc","") for it in items]
            if not texts:
                st.info("No chunks available to visualize. Use Upload/Refresh to populate sources.")
                raise RuntimeError("No chunk texts for 3D viz")
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
            # Sanitize points for plotting and avoid degenerate all-zero cases
            pts = np.nan_to_num(pts, nan=0.0, posinf=0.0, neginf=0.0)
            if not np.any(pts) and len(texts) > 0:
                rng = np.random.default_rng(42)
                pts = pts + 1e-3 * rng.standard_normal(size=pts.shape)
            if px is None:
                st.warning("Plotly not installed; install plotly to enable interactive 3D scatter.")
            else:
                import pandas as pd
                df = pd.DataFrame({"x": pts[:,0], "y": pts[:,1], "z": pts[:,2], "label": labels, "text": [t[:160] for t in texts]})
                fig = px.scatter_3d(df, x="x", y="y", z="z", color="label", hover_name="label", hover_data={"text": True})
                fig.update_traces(marker=dict(size=4, opacity=0.85))
                fig.update_layout(margin=dict(l=0, r=0, b=0, t=0), template='plotly_dark', scene=dict(bgcolor='rgba(0,0,0,0)'))
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"3D visualization error: {e}")

    # Global keyboard shortcut hints
    command_palette_hint()


if __name__ == "__main__":
    build_ui()
