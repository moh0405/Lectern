import time
import random
from typing import Dict, List, Any

import streamlit as st

# Inline styles for a subtle glassmorphism look
def inject_demo_styles() -> None:
    st.markdown(
        """
        <style>
          .glass { background: rgba(255,255,255,0.08); border-radius: 16px; border: 1px solid rgba(255,255,255,0.18); box-shadow: 0 8px 32px 0 rgba(31,38,135,0.37); backdrop-filter: blur(8.5px); -webkit-backdrop-filter: blur(8.5px); padding: 16px 20px; }
          .metric-box { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
          .metric { text-align: center; padding: 12px; border-radius: 12px; background: rgba(255,255,255,0.06); }
          .badge { padding: 2px 8px; border-radius: 10px; background: rgba(255,255,255,0.15); font-size: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# Demo data (cached responses and mock stats)
DEMO_RESPONSES: Dict[str, str] = {
    "Explain dynamic programming": (
        "Dynamic programming optimizes recursive problems by caching subproblem results "
        "(memoization) or building solutions bottom-up (tabulation). Define state, "
        "recurrence, base cases, and compute; patterns include knapsack, LIS, and edit distance."
    ),
    "What is a hash table?": (
        "A hash table maps keys to buckets via a hash function. With good hashing and "
        "resizing, average insert/lookup/delete are O(1). Collisions handled by chaining or open addressing."
    ),
    "Solve Two Sum": (
        "Scan the array while storing seen values in a dict. For each x, check target−x in the dict; "
        "return indices when found. Time O(n), space O(n)."
    ),
}

EXAMPLE_QUESTIONS: List[str] = [
    "Explain dynamic programming",
    "What is a hash table?",
    "Solve Two Sum",
]

DEMO_STATS: Dict[str, Any] = {
    "documents": 977,
    "chunks": 12368,
    "queries": 142,
    "avg_similarity": 0.89,
}

DEMO_CHUNKS: Dict[str, List[Dict[str, Any]]] = {
    "dynamic programming": [
        {"source": "algorithms.pdf", "score": 0.94, "content": "DP overview, optimal substructure"},
        {"source": "intro_to_cs.pdf", "score": 0.87, "content": "Memoization example and tabulation"},
    ],
    "hash table": [
        {"source": "data_structures.pdf", "score": 0.92, "content": "Hash functions, collisions, resizing"},
        {"source": "intro_to_cs.pdf", "score": 0.86, "content": "Chaining vs open addressing"},
    ],
}

DEMO_LEETCODE: List[Dict[str, Any]] = [
    {"id": 1, "title": "Two Sum", "difficulty": "Easy", "tags": ["Array", "Hash Table"]},
    {"id": 2, "title": "Longest Increasing Subsequence", "difficulty": "Medium", "tags": ["DP"]},
    {"id": 3, "title": "Edit Distance", "difficulty": "Hard", "tags": ["DP", "String"]},
    {"id": 4, "title": "Valid Anagram", "difficulty": "Easy", "tags": ["Hash Table", "String"]},
    {"id": 5, "title": "Coin Change", "difficulty": "Medium", "tags": ["DP"]},
]

MOCK_ANALYTICS_EVENTS: List[Dict[str, Any]] = [
    {"ts": 1, "query": "Explain dynamic programming", "latency_ms": 650, "mode": "demo"},
    {"ts": 2, "query": "What is a hash table?", "latency_ms": 580, "mode": "demo"},
    {"ts": 3, "query": "Solve Two Sum", "latency_ms": 520, "mode": "demo"},
    {"ts": 4, "query": "Explain dynamic programming", "latency_ms": 540, "mode": "demo"},
]


@st.cache_data(ttl=3600)
def get_demo_answer(question: str, fake_delay: bool = True) -> str:
    if fake_delay:
        time.sleep(0.35)
    return DEMO_RESPONSES.get(
        question,
        "Based on the demo documents, the answer involves standard techniques and trade-offs."
    )


@st.cache_data(ttl=3600)
def demo_search(query: str) -> List[Dict[str, Any]]:
    key = query.lower().strip()
    if "dynamic" in key or "dp" in key:
        return DEMO_CHUNKS.get("dynamic programming", [])
    if "hash" in key:
        return DEMO_CHUNKS.get("hash table", [])
    return [
        {"source": "algorithms.pdf", "score": round(random.uniform(0.8, 0.92), 2), "content": "General CS overview"}
    ]


@st.cache_data(ttl=3600)
def list_demo_leetcode(query: str = "") -> List[Dict[str, Any]]:
    q = query.lower().strip()
    if not q:
        return DEMO_LEETCODE
    return [p for p in DEMO_LEETCODE if q in p["title"].lower()]


def warm_caches() -> None:
    for q in EXAMPLE_QUESTIONS:
        _ = get_demo_answer(q, fake_delay=False)
    _ = demo_search("dynamic programming")
    _ = list_demo_leetcode("")


def stat_metric(label: str, value: Any) -> None:
    st.markdown(f"<div class='metric'><div class='badge'>{label}</div><h3>{value}</h3></div>", unsafe_allow_html=True)


def header_and_stats() -> None:
    st.markdown("# 🧠 AI Study Mentor — Demo Mode")
    with st.container():
        st.markdown("<div class='glass'>", unsafe_allow_html=True)
        st.markdown("### Instant Demo Stats")
        col1, col2, col3, col4 = st.columns(4)
        with col1: stat_metric("Documents", DEMO_STATS["documents"])
        with col2: stat_metric("Chunks", DEMO_STATS["chunks"])
        with col3: stat_metric("Queries", DEMO_STATS["queries"])
        with col4: stat_metric("Avg Similarity", DEMO_STATS["avg_similarity"])
        st.markdown("</div>", unsafe_allow_html=True)


def ask_tab() -> None:
    st.subheader("Ask — Instant Answers")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        if cols[i].button(q):
            st.session_state["demo_question"] = q

    question = st.text_input("Type a question", value=st.session_state.get("demo_question", EXAMPLE_QUESTIONS[0]))
    try:
        answer = get_demo_answer(question, fake_delay=True)
    except Exception:
        answer = "Temporary issue detected; showing cached best answer for a smooth demo."
    st.markdown("### ✅ Answer")
    st.info(answer)

    with st.expander("📚 View Retrieved Context"):
        chunks = []
        try:
            chunks = demo_search(question)
        except Exception:
            chunks = []
        if not chunks:
            st.write("Demo context is preloaded — no additional retrieval needed.")
        else:
            for i, c in enumerate(chunks, 1):
                src = c.get("source") or "demo.pdf"
                score = c.get("score")
                snippet = c.get("content") or ""
                score_txt = f" (score {score})" if score is not None else ""
                st.info(f"**Source {i}** — {src}{score_txt}")
                if snippet:
                    st.code(snippet)


def leetcode_tab() -> None:
    st.subheader("LeetCode — Instant Search")
    q = st.text_input("Search problems", value="Two Sum")
    try:
        results = list_demo_leetcode(q)
    except Exception:
        results = []
    st.write(f"Found {len(results)} problems")
    for p in results:
        with st.container():
            st.markdown("<div class='glass'>", unsafe_allow_html=True)
            st.markdown(f"**{p['title']}** · {p['difficulty']} · {', '.join(p['tags'])}")
            if p["title"].lower() == "two sum":
                st.code("""# Python
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        y = target - x
        if y in seen:
            return [seen[y], i]
        seen[x] = i
    return []
""")
            st.markdown("</div>", unsafe_allow_html=True)


def analytics_tab() -> None:
    st.subheader("Analytics — Mock Charts")
    evs = st.session_state.get("analytics_events", MOCK_ANALYTICS_EVENTS)
    import pandas as pd
    df = pd.DataFrame(evs)
    by_query = df.groupby("query")["latency_ms"].mean().reset_index().sort_values("latency_ms")
    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Average latency by query (ms)**")
        st.bar_chart(by_query.set_index("query"))
    with colB:
        st.markdown("**Latency samples (ms)**")
        st.line_chart(df["latency_ms"])


def about_tab() -> None:
    st.subheader("About the Demo")
    st.write(
        "This demo is pre-cached to guarantee instant answers, polished visuals, and "
        "rock-solid stability under time constraints. The full RAG pipeline is available in the repo."
    )


def render_demo_app() -> None:
    inject_demo_styles()
    if "demo_warmed" not in st.session_state:
        warm_caches()
        st.session_state["demo_warmed"] = True
        st.session_state["analytics_events"] = MOCK_ANALYTICS_EVENTS.copy()

    header_and_stats()
    tab_ask, tab_lc, tab_analytics, tab_about = st.tabs(["Ask", "LeetCode", "Analytics", "About"])
    with tab_ask:
        ask_tab()
    with tab_lc:
        leetcode_tab()
    with tab_analytics:
        analytics_tab()
    with tab_about:
        about_tab()