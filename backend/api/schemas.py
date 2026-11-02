"""Request/response models. These define the OpenAPI schema the TypeScript client is generated from."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

StudyMode = Literal["eli5", "technical", "interview", "summary"]
EliLevel = Literal["ELI5", "ELI10", "Undergrad", "Grad", "Expert"]
JobStatus = Literal["queued", "running", "done", "failed"]


# ---------------------------------------------------------------- shared
class Chunk(BaseModel):
    text: str
    doc: str
    page: Optional[int] = None
    end_page: Optional[int] = Field(None, description="Set when the passage runs onto the next page of a PDF (so it spans page..end_page)")
    score: float
    url: Optional[str] = None
    citation_url: Optional[str] = Field(None, description="Deep link to the cited spot (for example a YouTube timestamp) when available")


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    semantic_search: bool = Field(description="True when the embedder matching the index is loaded")
    chunks: int


# ---------------------------------------------------------------- sources / documents
class FileResult(BaseModel):
    filename: str
    size_bytes: int = 0
    ok: bool
    error: Optional[str] = None


class SourcesAccepted(BaseModel):
    job_id: Optional[str] = Field(None, description="Poll GET /api/v1/jobs/{job_id}; null if nothing was accepted")
    files: List[FileResult]
    urls: List[str]


class UrlsRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=20, description="http(s) URLs: YouTube, GitHub repo, or web article")


class Job(BaseModel):
    id: str
    kind: str
    status: JobStatus
    progress: List[str]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float
    finished_at: Optional[float] = None


class DocumentInfo(BaseModel):
    source_key: str = Field(description="File name or URL; pass it to DELETE /api/v1/sources/{source_key}")
    docs: List[str]
    chunks: int
    source_type: Optional[str] = None


class DocumentsResponse(BaseModel):
    documents: List[DocumentInfo]


class Stats(BaseModel):
    documents: int
    chunks: int
    min_page: Optional[int] = None
    max_page: Optional[int] = None
    embedder: Optional[str] = None
    semantic_search: bool


class DeleteResult(BaseModel):
    ok: bool
    deleted: str
    chunks_removed: int


# ---------------------------------------------------------------- ask
class CitationCheck(BaseModel):
    label: str = Field(description="The citation as the model wrote it, e.g. 'Dsa.pdf (page 12)'")
    doc: str
    page: Optional[int] = None
    status: Literal["ok", "page_not_retrieved", "unknown_source"] = Field(
        description="ok: among the retrieved passages. page_not_retrieved: that document was retrieved, but not this page. "
        "unknown_source: that document was not retrieved at all (possibly invented)."
    )


class ContextPassage(BaseModel):
    """A passage the caller already retrieved (for example from documents that live only in the visitor's browser)."""

    text: str = Field(..., min_length=1, max_length=4000)
    doc: str = Field(..., min_length=1, max_length=300)
    page: Optional[int] = Field(None, ge=1, le=100000)
    end_page: Optional[int] = Field(None, ge=1, le=100000)
    score: float = 0.0


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    k: int = Field(3, ge=1, le=20, description="Number of chunks to retrieve")
    mode: Optional[StudyMode] = None
    model: Optional[str] = Field(None, max_length=100)
    temperature: float = Field(0.2, ge=0.0, le=1.0)
    include_prompt: bool = False
    no_cache: bool = Field(False, description="Skip the answer cache and ask the model again")
    context: Optional[List[ContextPassage]] = Field(
        None,
        max_length=20,
        description="Answer from these passages instead of the server's index. Nothing is stored, cached or recorded in analytics.",
    )


class AgentAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    k: int = Field(3, ge=1, le=10, description="Number of passages to answer from")
    mode: Optional[StudyMode] = None
    model: Optional[str] = Field(None, max_length=100)
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class AskResponse(BaseModel):
    answer: str
    chunks: List[Chunk]
    model: Optional[str] = None
    prompt: Optional[str] = None
    citations: List[CitationCheck] = Field(description="Citations found in the answer, each checked against the retrieved passages")
    unverified_citations: int = Field(description="How many citations are not among the retrieved passages")
    uncited: bool = Field(description="True when passages were retrieved and the answer is long but cites none of them")
    cached: bool = Field(description="True when this answer came from the cache instead of a new model call")


class Models(BaseModel):
    models: List[str] = Field(description="Model names that can generate text for the configured key, newest Flash first")
    default: str


class SearchResponse(BaseModel):
    chunks: List[Chunk]


class Suggestions(BaseModel):
    questions: List[str]


# ---------------------------------------------------------------- tutor tools
class TopicRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class ConceptNode(BaseModel):
    id: str
    label: str


class ConceptEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    label: Optional[str] = None

    model_config = {"populate_by_name": True}


class ConceptMap(BaseModel):
    nodes: List[ConceptNode]
    edges: List[ConceptEdge]
    dot: str = Field(description="Graphviz DOT source")
    model: Optional[str] = None
    warning: Optional[str] = Field(None, description="Set when an offline fallback was used instead of the model")


class SocraticRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    depth: int = Field(0, ge=0, le=5, description="Higher means the student has struggled more")
    k: int = Field(3, ge=0, le=10)
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class Socratic(BaseModel):
    questions: List[str]
    hints: List[str]
    model: Optional[str] = None
    warning: Optional[str] = None


class SynthesisRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    k_per_doc: int = Field(2, ge=1, le=5)
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class SynthesisCitation(BaseModel):
    doc: str
    point: str


class Synthesis(BaseModel):
    similarities: List[str]
    conflicts: List[str]
    synthesis: str
    citations: List[SynthesisCitation]
    model: Optional[str] = None
    warning: Optional[str] = None


class AdaptiveRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    level: EliLevel = "Undergrad"
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class Adaptive(BaseModel):
    answer: str
    chunks: List[Chunk]
    level: EliLevel
    model: Optional[str] = None
    warning: Optional[str] = None


class MathRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=200, examples=["differentiate sin(x)", "solve x^2 = 4 for x"])


class MathResult(BaseModel):
    kind: str
    latex: str
    steps: List[str]


# ---------------------------------------------------------------- LeetCode
class ProblemSummary(BaseModel):
    pid: str
    title: str
    difficulty: str
    topics: List[str]
    acceptance: Optional[float] = None
    likes: Optional[int] = None
    dislikes: Optional[int] = None
    url: Optional[str] = None
    score: Optional[float] = None
    source: Optional[str] = None


class Problem(ProblemSummary):
    description: str


class ProblemSearch(BaseModel):
    problems: List[ProblemSummary]


class ProblemStats(BaseModel):
    total: int
    by_difficulty: Dict[str, int]
    top_topics: List[List[Any]] = Field(description="[[topic, count], ...] most common first")


class Explanation(BaseModel):
    markdown: str
    model: Optional[str] = None


# ---------------------------------------------------------------- study tools
class HistoryItem(BaseModel):
    q: str = Field(..., max_length=2000)
    answer: str = Field("", max_length=20000)


class NotesRequest(BaseModel):
    history: List[HistoryItem] = Field(..., min_length=1, max_length=50)
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class Notes(BaseModel):
    markdown: str
    model: Optional[str] = None


class ExportRequest(BaseModel):
    markdown: str = Field(..., min_length=1, max_length=200_000)
    format: Literal["pdf", "html", "md"] = "pdf"
    filename: str = Field("study-notes", max_length=80, pattern=r"^[A-Za-z0-9_\- ]+$")


class AnalyticsEvent(BaseModel):
    id: int
    ts: float
    question: str
    avg_score: float
    latency_ms: int
    tokens_prompt: int
    tokens_answer: int
    mode: Optional[str] = None
    docs: List[str]
    ok: bool


class AnalyticsSummary(BaseModel):
    queries: int
    avg_score: float
    avg_latency_ms: float
    tokens_prompt: int
    tokens_answer: int
    doc_usage: Dict[str, int]
    streak_days: int
    recent: List[AnalyticsEvent]


class Cleared(BaseModel):
    ok: bool
    removed: int


# ---------------------------------------------------------------- visualization
class ProjectionPoint(BaseModel):
    x: float
    y: float
    z: float
    doc: str
    page: Optional[int] = None
    text: str = Field(description="First 200 characters of the passage")
    index: int = Field(description="Position of the passage in the index")


class Projection(BaseModel):
    points: List[ProjectionPoint]
    explained_variance: List[float] = Field(description="Share of the variance kept by each of the three axes")
    method: Literal["pca"]
    embedder: Optional[str]
    semantic: bool = Field(description="False for the hashing embedder: closeness reflects shared words, not meaning")
    total_chunks: int


# ---------------------------------------------------------------- flashcards (spaced repetition)
class CardCreate(BaseModel):
    front: str = Field(..., min_length=1, max_length=1200)
    back: str = Field(..., min_length=1, max_length=1200)
    source: Optional[str] = Field(None, max_length=300, description="Where the card came from, for example a document name")


class Card(BaseModel):
    id: int
    front: str
    back: str
    source: Optional[str] = None
    created_at: float
    due_at: float = Field(description="Epoch seconds; the card is due when this is in the past")
    interval_days: int
    ef: float = Field(description="SM-2 ease factor (never below 1.3)")
    repetitions: int
    lapses: int
    reviews: int
    last_reviewed: Optional[float] = None


class CardStats(BaseModel):
    total: int
    due: int
    new_cards: int
    mature: int = Field(description="Cards with an interval of 21 days or more")
    reviews: int


class CardList(BaseModel):
    cards: List[Card]
    stats: CardStats


class ReviewRequest(BaseModel):
    grade: int = Field(..., ge=0, le=5, description="SM-2 grade: 0 blackout .. 5 perfect. The UI buttons use again=1, hard=3, good=4, easy=5")


class GenerateCardsRequest(BaseModel):
    topic: Optional[str] = Field(None, max_length=200, description="Focus on this topic; omit to sample your whole material")
    n: int = Field(5, ge=1, le=15)
    temperature: float = Field(0.2, ge=0.0, le=2.0)


# ---------------------------------------------------------------- LeetCode progress and plan
ProgressStatus = Literal["todo", "attempted", "solved"]


class ProgressUpdate(BaseModel):
    status: ProgressStatus
    notes: Optional[str] = Field(None, max_length=4000, description="Omit to keep the existing notes")


class ProgressItem(BaseModel):
    pid: str
    title: str
    status: ProgressStatus
    notes: str
    attempts: int
    difficulty: str
    topics: List[str]
    updated_at: float
    solved_at: Optional[float] = None


class ProgressSummary(BaseModel):
    solved: int
    attempted: int
    todo: int
    solved_by_difficulty: Dict[str, int]


class ProgressList(BaseModel):
    items: List[ProgressItem]
    summary: ProgressSummary


class TopicStat(BaseModel):
    topic: str
    attempted: int
    solved: int
    solve_rate: float


class PlanItem(BaseModel):
    pid: str
    title: str
    difficulty: str
    topics: List[str]
    reason: str


class StudyPlan(BaseModel):
    weak_topics: List[str] = Field(description="Topics you attempted but solved under half of")
    topics: List[TopicStat]
    items: List[PlanItem]


# ---------------------------------------------------------------- saved Ask history
class HistoryTurn(BaseModel):
    question: str = Field(..., max_length=2000)
    answer: str = Field("", max_length=20000)
    mode: Optional[str] = None
    model: Optional[str] = None
    cached: bool = False
    chunks: List[Chunk] = []
    citations: List[CitationCheck] = []
    unverified_citations: int = 0
    uncited: bool = False


class SavedTurn(HistoryTurn):
    id: int
    ts: float


class SavedHistory(BaseModel):
    turns: List[SavedTurn]


# ---------------------------------------------------------------- SSE payloads (POST /ask/stream)
class SseMeta(BaseModel):
    chunks: List[Chunk]
    prompt: Optional[str] = None


class SseToken(BaseModel):
    text: str


class SseDone(BaseModel):
    model: Optional[str] = None
    citations: List[CitationCheck]
    unverified_citations: int
    uncited: bool
    cached: bool


class SseStep(BaseModel):
    name: Literal["rewrite", "retrieve", "grade", "answer", "verify", "regenerate"]
    detail: str


class SseReplace(BaseModel):
    reason: str


class SseAgentDone(SseDone):
    llm_calls: int = Field(description="Model calls this question used (at most 6)")
    regenerated: bool = Field(description="True when the first answer cited unknown sources and was rewritten")


class SseError(BaseModel):
    code: Literal["retrieval_error", "llm_unavailable", "llm_error"]
    message: str
