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
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    k: int = Field(3, ge=1, le=20, description="Number of chunks to retrieve")
    mode: Optional[StudyMode] = None
    model: Optional[str] = Field(None, max_length=100)
    temperature: float = Field(0.2, ge=0.0, le=1.0)
    include_prompt: bool = False


class AskResponse(BaseModel):
    answer: str
    chunks: List[Chunk]
    model: Optional[str] = None
    prompt: Optional[str] = None


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


# ---------------------------------------------------------------- SSE payloads (POST /ask/stream)
class SseMeta(BaseModel):
    chunks: List[Chunk]
    prompt: Optional[str] = None


class SseToken(BaseModel):
    text: str


class SseDone(BaseModel):
    model: Optional[str] = None


class SseError(BaseModel):
    code: Literal["retrieval_error", "llm_unavailable", "llm_error"]
    message: str
