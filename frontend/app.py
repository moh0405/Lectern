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
import json
from pathlib import Path
from typing import List, Dict, Any

import streamlit as st

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.rag_engine import RAGEngine
from backend.llm_config import GeminiClient
from backend.document_processor import discover_inputs, list_chunks_from_dir
from backend.export_utils import markdown_to_pdf, markdown_to_html
from backend.advanced_ai import build_concept_map, concept_map_to_dot
from backend.leetcode_handler import LeetCodeHandler
import random
import pandas as pd


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
            engine = RAGEngine.shared()
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
    # Initialize lightweight analytics store for the Analytics tab
    if "analytics" not in st.session_state:
        st.session_state["analytics"] = {
            "session_start": time.time(),
            "events": [],  # {ts, q, avg_sim, latency_ms, tokens_prompt, tokens_answer, docs}
            "doc_usage": {},
            "streak_days": 0,
        }
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

        # Study Mode selector
        mode = st.selectbox(
            "Study Mode",
            options=["ELI5", "Technical", "Interview Prep", "Quick Summary"],
            index=1,
            help="Changes the prompt template and answer style",
        )

        st.divider()
        st.subheader("Upload & URLs")
        st.caption("Drop PDFs or paste links (GitHub, docs, YouTube). Click Process.")
        files = st.file_uploader("Upload PDF(s)", type=["pdf"], accept_multiple_files=True)
        urls_text = st.text_area("Paste URLs", placeholder="https://docs.python.org/...\nhttps://github.com/...\nhttps://www.youtube.com/watch?v=...")
        ingest = st.button("Process Sources")

        if ingest:
            with st.spinner("Processing sources…"):
                try:
                    out_dir = PROJECT_ROOT / "data" / "uploaded_files"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    # Save PDFs
                    saved = []
                    for f in (files or []):
                        dest = out_dir / f.name
                        dest.write_bytes(f.getbuffer())
                        saved.append(f.name)
                    # Save URLs list for downstream scanners (into sources.txt)
                    urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
                    if urls:
                        (out_dir / "sources.txt").write_text("\n".join(urls))
                    # Warm metadata + show summary
                    RAGEngine.shared().add_sources(discover_inputs(str(out_dir.resolve())))
                    chunks = RAGEngine.shared()._docstore_iter()
                    by_doc = {}
                    for it in chunks:
                        d = it.get("doc") or "unknown"
                        by_doc[d] = by_doc.get(d, 0) + 1
                    st.success(
                        f"Processed {len(saved)} PDF(s), {len(urls)} URL(s). Collected {len(chunks)} chunks.")
                    st.caption("Per‑document chunk counts")
                    import pandas as _pd
                    st.dataframe(_pd.DataFrame(sorted(by_doc.items(), key=lambda x: -x[1]), columns=["Document","Chunks"]))
                except Exception as e:
                    st.error(f"Ingestion error: {e}")
                    toast("Sources processed successfully", "success")
                except Exception as e:
                    st.error(f"Ingest error: {e}")

    # Stats dashboard on top
    engine = RAGEngine.shared()
    stats = stats_panel(engine)
    c1, c2, c3 = st.columns(3)
    c1.metric("Documents", stats["documents"])
    c2.metric("Chunks", stats["chunks"])
    if "query_count" not in st.session_state:
        st.session_state["query_count"] = 0
    c3.metric("Queries", st.session_state["query_count"]) 

    # Intelligent Query Suggestions
    st.caption("Smart Suggestions from your corpus")
    try:
        suggestions = RAGEngine.shared().generate_query_suggestions(max_questions=5, model=model, temperature=temperature)
    except Exception:
        suggestions = [
            "Explain dynamic programming",
            "Difference between BFS and DFS",
            "How do hash tables handle collisions?",
            "What is a balanced binary search tree?",
            "Describe Dijkstra vs Bellman-Ford",
        ]
    sug_cols = st.columns(min(5, len(suggestions)))
    for i, q_s in enumerate(suggestions):
        if sug_cols[i].button(q_s):
            st.session_state["question"] = q_s
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
        start_t = time.time()
        thinking_msgs = [
            "Analyzing structures…",
            "Balancing trees…",
            "Hashing thoughts…",
            "Traversing graphs…",
            "Dynamic programming in progress…",
        ]
        st.info(random.choice(thinking_msgs))
        # Step: retrieve
        with ctx_col:
            st.subheader("Context")
            try:
                chunks = engine.retrieve_context(question, k=k)
                retrieved_chunks = chunks
                st.success(f"Retrieved {len(chunks)} chunk(s)")
                for c in chunks:
                    chunk_card(c, question)
                # Similarity scores graph (simple bar)
                try:
                    df_scores = pd.DataFrame({"chunk": [f"{c.get('doc')} p{c.get('page')}" for c in chunks], "score": [float(c.get('score') or 0.0) for c in chunks]})
                    st.caption("Similarity scores")
                    st.bar_chart(df_scores.set_index("chunk"))
                except Exception:
                    pass
            except Exception as e:
                st.error(f"Retrieval error: {e}")

        # Step: generate (streaming-like)
        with a_col:
            st.subheader("Answer")
            ph = st.empty()
            try:
                result = engine.answer_with_gemini(question, k=k, model=model, temperature=temperature, mode=mode)
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
                elapsed = time.time() - start_t
                st.caption(f"Response time: {elapsed:.2f}s")
                # track metrics
                metrics = st.session_state.setdefault("metrics", {"times": []})
                metrics["times"].append(elapsed)
                toast("Answer generated", "success")

                # Record event for Analytics tab
                try:
                    sims = [float(c.get("score") or 0.0) for c in (retrieved_chunks or [])]
                    avg_sim = sum(sims)/len(sims) if sims else 0.0
                    prompt = answer_result.get("prompt", "")
                    answer = answer_result.get("answer", "")
                    tokens_prompt = int(len(prompt)/4)
                    tokens_answer = int(len(answer)/4)
                    docs = [c.get("doc") or (c.get("url") or "") for c in (retrieved_chunks or [])]
                    ev = {
                        "ts": time.time(),
                        "q": question,
                        "avg_sim": avg_sim,
                        "latency_ms": int(elapsed*1000),
                        "tokens_prompt": tokens_prompt,
                        "tokens_answer": tokens_answer,
                        "docs": docs,
                    }
                    st.session_state["analytics"]["events"].append(ev)
                    # doc usage counts
                    du = st.session_state["analytics"]["doc_usage"]
                    for d in docs:
                        if not d:
                            continue
                        du[d] = du.get(d, 0) + 1
                    # streak days heuristic
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
            except Exception as e:
                st.error(f"Generation error: {e}")

        # Chat history
        hist = st.session_state.setdefault("history", [])
        hist.append({"q": question, "answer": answer_result.get("answer", ""), "chunks": retrieved_chunks})

        # Progressive learning tracker
        tracker = st.session_state.setdefault("learning", {})
        toks = set(re.findall(r"\b\w+\b", question.lower()))
        for t in toks:
            if len(t) <= 2:
                continue
            d = tracker.get(t, {"asked": 0})
            d["asked"] += 1
            tracker[t] = d

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
        # Flashcards CSV (Q, A)
        try:
            import io
            import csv
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["Question", "Answer"])
            for h in hist:
                writer.writerow([h["q"], (h.get("answer") or "").strip()])
            st.download_button("Download flashcards (CSV)", data=buf.getvalue(), file_name="flashcards.csv", mime="text/csv")
        except Exception:
            pass

        # Generate study notes (summary) and export PDF
        st.divider()
        if st.button("Generate Study Notes (Markdown)"):
            with st.spinner("Summarizing session…"):
                try:
                    engine2 = RAGEngine.shared()
                    summ = engine2.summarize_chat(hist, model=model, temperature=temperature)
                    if summ.get("ok"):
                        notes_md = summ.get("markdown") or ""
                        st.session_state["study_notes_md"] = notes_md
                        st.markdown(notes_md)
                        # Offer PDF
                        pdf_bytes = markdown_to_pdf(notes_md)
                        if pdf_bytes:
                            st.download_button("Download Study Notes (PDF)", data=pdf_bytes, file_name="study_notes.pdf", mime="application/pdf")
                        else:
                            html = markdown_to_html(notes_md)
                            st.download_button("Download Study Notes (HTML)", data=html, file_name="study_notes.html", mime="text/html")
                        toast("Study notes generated", "success")
                    else:
                        st.error(summ.get("error", "Failed to summarize"))
                except Exception as e:
                    st.error(f"Summary error: {e}")

    # Learning Tracker view and follow-ups
    st.divider()
    st.subheader("Learning Tracker")
    tracker = st.session_state.get("learning", {})
    learned = st.session_state.setdefault("learned_topics", set())
    review = st.session_state.setdefault("review_topics", set())
    if not tracker:
        st.caption("Ask questions to populate topics.")
    else:
        df_t = pd.DataFrame(sorted([(k, v.get("asked", 0)) for k, v in tracker.items()], key=lambda x: -x[1]), columns=["topic","asked"])
        st.dataframe(df_t, height=220)
        st.caption("Mark topics")
        cols = st.columns(3)
        sel = cols[0].selectbox("Select topic", options=[t for t in df_t["topic"].values])
        if cols[1].button("Mark learned"):
            learned.add(sel)
        if cols[2].button("Mark review"):
            review.add(sel)
        st.write(f"Learned: {sorted(list(learned))[:10]}")
        st.write(f"Review needed: {sorted(list(review))[:10]}")
        # visualize gap
        try:
            scores = []
            for t in df_t["topic"].values:
                base = int(tracker[t]["asked"]) if t in tracker else 0
                adjust = -1 if t in review else (1 if t in learned else 0)
                scores.append(base + adjust)
            st.caption("Knowledge coverage (adjusted by learned/review)")
            st.bar_chart(pd.DataFrame({"topic": df_t["topic"].values, "coverage": scores}).set_index("topic"))
        except Exception:
            pass

        # follow-up suggestions for low-frequency or review topics
        low = [t for t, n in df_t.values if n == 1]
        follow = list({*low, *list(review)})[:5]
        if follow:
            st.caption("Follow-up suggestions")
            fcols = st.columns(min(5, len(follow)))
            for i, t in enumerate(follow):
                if fcols[i].button(f"Explain {t}"):
                    st.session_state["question"] = f"Explain {t}"
                    st.experimental_rerun()

    # Multi-Source Synthesis (compare answers)
    st.divider()
    st.subheader("Multi-Source Synthesis")
    synth_q = st.text_input("Topic to synthesize", value="Linked lists vs arrays")
    if st.button("Compare sources"):
        with st.spinner("Synthesizing across sources…"):
            try:
                res = RAGEngine.shared().multi_source_synthesis(synth_q, k_per_doc=2, model=model, temperature=temperature)
                if res.get("ok"):
                    st.markdown(res.get("answer",""))
                    st.caption("Citations")
                    for c in res.get("citations", [])[:8]:
                        st.markdown(f"- {c.get('doc')} (page {c.get('page')})")
                else:
                    st.error(res.get("error","Synthesis failed"))
            except Exception as e:
                st.error(f"Synthesis error: {e}")

    # Real-time metrics section
    st.divider()
    st.subheader("Real-Time Metrics")
    metrics = st.session_state.get("metrics", {"times": []})
    times = metrics.get("times", [])
    avg_t = sum(times) / len(times) if times else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric("Total queries", st.session_state.get("query_count", 0))
    c2.metric("Avg response time", f"{avg_t:.2f}s")
    c3.metric("Top‑k", st.session_state.get("last_k", k))
    if times:
        st.line_chart(pd.DataFrame({"response_time": times}))

    # Extra tabs: Concept Map, LeetCode, and Analytics
    tab_map, tab_leetcode, tab_analytics = st.tabs(["Concept Map", "LeetCode", "Analytics"])

    # Concept Map tab
    with tab_map:
        st.subheader("Concept Map Generator")
        topic = st.text_input("Topic", value="Machine Learning")
        gen = st.button("Generate Concept Map")
        if gen:
            try:
                result = build_concept_map(topic, temperature=temperature)
                if result.get("ok"):
                    nodes = result.get("nodes", [])
                    edges = result.get("edges", [])
                    dot = concept_map_to_dot(nodes, edges)
                    st.graphviz_chart(dot, use_container_width=True)
                    node_ids = [n.get("id") or n.get("label") for n in nodes]
                    selected = st.selectbox("Inspect concept", options=node_ids) if node_ids else None
                    if selected:
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
            except Exception as e:
                st.error(f"Concept map error: {e}")

    # LeetCode tab
    with tab_leetcode:
        st.subheader("LeetCode Practice + Mentor")
        # Ensure handler in session
        if "leetcode_handler" not in st.session_state:
            st.session_state["leetcode_handler"] = LeetCodeHandler()
        lc: LeetCodeHandler = st.session_state["leetcode_handler"]

        c1, c2 = st.columns([1, 2])
        if c1.button("Load/Refresh Datasets"):
            with st.spinner("Loading LeetCode datasets…"):
                try:
                    n, status = lc.load_all()
                    st.success(f"Loaded {n} problems ({status})")
                except Exception as e:
                    st.error(f"LeetCode load failed: {e}")
        if lc.is_loaded():
            stats = lc.get_stats()
            c2.metric("Problems", stats.get("total", 0))
            by_diff = stats.get("by_difficulty", {})
            d1, d2, d3 = st.columns(3)
            d1.metric("Easy", by_diff.get("Easy", 0))
            d2.metric("Medium", by_diff.get("Medium", 0))
            d3.metric("Hard", by_diff.get("Hard", 0))

        st.divider()
        query = st.text_input("Search problems", value="binary tree traversal")
        left, right = st.columns([1, 2])
        difficulties = left.multiselect("Difficulty", options=["Easy", "Medium", "Hard"], default=["Easy", "Medium", "Hard"]) 
        topic_str = left.text_input("Topics (comma-separated)", value="Tree, DFS, BFS")
        topics = [t.strip() for t in topic_str.split(",") if t.strip()]
        top_k = right.slider("Top K", min_value=5, max_value=30, value=10)
        run = right.button("Search")

        results = []
        if run:
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

                    # Explain button
                    exp_c1, exp_c2 = st.columns([1, 1])
                    if exp_c1.button("Explain & Guide", key=f"exp_{r['pid']}"):
                        with st.spinner("Generating study guide…"):
                            try:
                                out = lc.explain_problem(r["pid"], temperature=temperature, model=model)
                                if out.get("ok"):
                                    st.markdown(out.get("markdown") or "")
                                else:
                                    st.error(out.get("error"))
                            except Exception as e:
                                st.error(f"Explanation failed: {e}")

                    # Track analytics
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

    # Analytics tab
    with tab_analytics:
        st.subheader("Analytics Dashboard")
        evs = st.session_state["analytics"]["events"]
        if not evs:
            st.info("Run a few queries to populate analytics.")
        else:
            try:
                import plotly.express as px
                import pandas as _pd
                df = _pd.DataFrame(evs)

                st.markdown("**Study Analytics**")
                sa1, sa2, sa3 = st.columns(3)
                total_time_min = int((time.time() - st.session_state["analytics"]["session_start"]) / 60)
                sa1.metric("Time Spent (min)", total_time_min)
                sa2.metric("Questions", len(evs))
                sa3.metric("Streak (days)", st.session_state["analytics"].get("streak_days", 1))

                # Topics tag cloud from questions
                st.caption("Topics explored")
                tokens = {}
                for q in df["q"].tolist():
                    for t in re.findall(r"\b\w+\b", str(q).lower()):
                        if len(t) <= 2:
                            continue
                        tokens[t] = tokens.get(t, 0) + 1
                tags = sorted(tokens.items(), key=lambda x: x[1], reverse=True)[:30]
                cloud = " ".join([f"<span style='font-size:{12+v*2}px;color:#cbd5e1;margin:4px;display:inline-block'>{k}</span>" for k,v in tags])
                st.markdown(f"<div class='card'>{cloud}</div>", unsafe_allow_html=True)

                st.markdown("**RAG Performance**")
                c1, c2 = st.columns(2)
                fig_sim = px.line(df, y="avg_sim", title="Avg Similarity over Queries")
                c1.plotly_chart(fig_sim, use_container_width=True)
                fig_lat = px.line(df, y="latency_ms", title="Response Latency (ms)")
                c2.plotly_chart(fig_lat, use_container_width=True)

                # Token usage
                if set(["tokens_prompt", "tokens_answer"]).issubset(df.columns):
                    fig_tok = px.area(df[["tokens_prompt", "tokens_answer"]], title="Token Usage (approx)")
                    st.plotly_chart(fig_tok, use_container_width=True)

                # Document Insights
                st.markdown("**Document Insights**")
                du = st.session_state["analytics"]["doc_usage"]
                if du:
                    df_du = _pd.DataFrame({"doc": list(du.keys()), "count": list(du.values())})
                    fig_docs = px.bar(df_du, x="doc", y="count", title="Most Queried Documents")
                    st.plotly_chart(fig_docs, use_container_width=True)
                else:
                    st.info("No document usage yet.")

                # Export report
                st.markdown("**Export**")
                report_md = "\n".join([f"- {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e['ts']))}: Q='{e['q']}', sim={e['avg_sim']:.2f}, lat={e['latency_ms']}ms" for e in evs])
                st.download_button("Download Study Report (Markdown)", data=report_md, file_name="study-report.md")
                import csv
                from io import StringIO
                sio = StringIO()
                writer = csv.DictWriter(sio, fieldnames=["ts","q","avg_sim","latency_ms","tokens_prompt","tokens_answer"]) 
                writer.writeheader()
                for e in evs:
                    writer.writerow({k: e.get(k) for k in writer.fieldnames})
                st.download_button("Export Analytics (CSV)", data=sio.get_value(), file_name="analytics.csv")
            except Exception as e:
                st.error(f"Analytics rendering error: {e}")


if __name__ == "__main__":
    build_ui()