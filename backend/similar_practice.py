"""Similar example: one new practice question on the same concept, written from the passages the student just read.

Up to two model calls, only when the student asks: a draft that fails a guard gets one more try, told only which guard
it failed. A provider, quota or spend-cap failure is never retried. The model also writes a one-sentence `answer_key`, which is never returned:
it is used to reject a question that gives its own answer away (`gives_answer_away`).
A question is only returned when it cites a passage it was given and shares content with that passage, so it stays
grounded, and when it is not a rewording of the original question or of one already offered.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .advanced_ai import _REVEAL_PATTERNS, _content_words
from .attempt_feedback import _check_item, _clean, _json, _passages
from .llm_providers import create_llm

logger = logging.getLogger("ai-study-mentor.similar")

MIN_CHARS = 12
MAX_CHARS = 500
MAX_CALLS = 2  # the first draft, and one more only if a guard rejected it
MAX_OVERLAP = 0.8  # share of content words above which a question counts as a rewording
MIN_GROUNDING_WORDS = 2
MAX_KEY_COVERAGE = 0.8  # share of the answer key's content words a question may not reach

UNAVAILABLE = "Lectern could not write a practice question from these passages. Try again."

PROMPT = """TASK: SIMILAR_QUESTION
You are a tutor writing one new practice question for a student who has just studied the ORIGINAL QUESTION.

Rules:
- Test the same concept as the original question, in a new situation, with new values or from a different angle.
- It must be answerable from the PASSAGES alone. Do not rely on anything they do not say.
- Do not reuse or lightly reword the original question or any question under ALREADY ASKED.
- Never include the answer, a hint toward it, worked steps, or answer choices in the question.
- One or two sentences, plain text, no code fences.

Cite the passage it is based on with its label exactly as it appears in square brackets, for example "notes.pdf (page 4)".
Also write "answer_key": the correct answer in one sentence. It is only used to check that the question does not give
it away and is never shown.

Return pure JSON:
{{"question": "...", "answer_key": "...", "citations": ["doc (page N)"]}}

ORIGINAL QUESTION: {question}

ALREADY ASKED:
{previous}

PASSAGES:
{passages}"""

RETRY_REASON = {
    "malformed": "it was not valid JSON with a question of one or two sentences and a one-sentence answer_key.",
    "leaks_answer": "the question gave its own answer away.",
    "rewording": "the question was too close to the original question or one already asked.",
    "ungrounded": "the question did not cite a listed passage or did not share content with the passage it cited.",
}
RETRY_NOTE = "\n\nYOUR PREVIOUS DRAFT WAS REJECTED: {reason} Write a different question that follows every rule above."


def build_prompt(question: str, chunks: Sequence[Dict[str, Any]], previous: Sequence[str] = (), rejected: Optional[str] = None) -> str:
    """The prompt. On a retry, `rejected` is the guard's name: the rejected draft and its key are never sent back."""
    asked = "\n".join(f"* {p}" for p in previous) or "(none)"
    prompt = PROMPT.format(question=question, previous=asked, passages=_passages(chunks))
    return prompt + RETRY_NOTE.format(reason=RETRY_REASON[rejected]) if rejected else prompt


def _overlap(a: str, b: str) -> float:
    x, y = _content_words(a), _content_words(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def _grounded(text: str, citations: List[Dict[str, Any]], chunks: Sequence[Dict[str, Any]]) -> bool:
    """A verified citation whose passage shares real content with the question."""
    words = _content_words(text)
    docs = {c.get("doc") for c in citations if c["status"] == "ok"}
    return any(c.get("doc") in docs and len(words & _content_words(c.get("text") or "")) >= MIN_GROUNDING_WORDS for c in chunks)


def interpret(data: Dict[str, Any], question: str, chunks: Sequence[Dict[str, Any]], previous: Sequence[str] = ()) -> Optional[Dict[str, Any]]:
    """The checked practice question, or None when it fails a guard."""
    return _judge(data, question, chunks, previous)[0]


def _judge(data: Dict[str, Any], question: str, chunks: Sequence[Dict[str, Any]],
           previous: Sequence[str] = ()) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(the checked question, None), or (None, the guard it failed). The answer key never leaves this function."""
    text = _clean(data.get("question"), MAX_CHARS + 1)
    key = data.get("answer_key") if isinstance(data.get("answer_key"), str) else ""
    if not MIN_CHARS <= len(text) <= MAX_CHARS or not key.strip():
        return None, _rejected("malformed")
    if gives_answer_away(text, key):
        return None, _rejected("leaks_answer")
    if any(_overlap(text, seen) >= MAX_OVERLAP for seen in [question, *previous]):
        return None, _rejected("rewording")
    raw = data.get("citations")
    labels = raw if isinstance(raw, list) else [raw] if isinstance(raw, str) else []
    citations = [c for c in _check_item("", labels, chunks) if c["status"] == "ok"]
    if not _grounded(text, citations, chunks):
        return None, _rejected("ungrounded")
    return {"question": text, "citations": citations}, None


def _rejected(reason: str) -> str:
    """Log only the guard's name: the question and its key are study content and stay out of the logs."""
    logger.info("Rejected a practice question: %s", reason)
    return reason


def gives_answer_away(text: str, key: str) -> bool:
    """Whether the question states its answer. A good question shares the answer's topic words (its premise), so shared
    vocabulary alone is not a leak: it leaks when it says "the answer is", or carries nearly all of the key's content."""
    if key.strip().lower() in text.lower() or _REVEAL_PATTERNS.search(text):
        return True
    answer = _content_words(key)
    shared = answer & _content_words(text)
    return len(shared) >= 3 and len(shared) / len(answer) >= MAX_KEY_COVERAGE


def similar_question(question: str, chunks: Sequence[Dict[str, Any]], previous: Sequence[str] = (), model: Optional[str] = None,
                     temperature: float = 0.4) -> Dict[str, Any]:
    """Write one practice question in at most two model calls, the second only after a guard rejected the first. Each
    call goes through the capped client, so both count. Returns {"ok": False, "error"} when none passes the guards."""
    chunks = [c for c in chunks if (c.get("text") or "").strip()]
    rejected: Optional[str] = None
    try:
        client = create_llm(model=model, temperature=temperature)
        for _ in range(MAX_CALLS):
            resp = client.generate(build_prompt(question, chunks, previous, rejected), json_mode=True)
            if not resp.get("ok"):  # provider, quota or spend-cap failure: never retried here
                return {"ok": False, "error": resp.get("error")}
            try:
                data = _json((resp.get("answer") or "").strip())
            except ValueError:
                result, rejected = None, _rejected("malformed")
            else:
                result, rejected = _judge(data, question, chunks, previous)
            if result is not None:
                return {"ok": True, **result, "model": resp.get("model")}
    except Exception as e:  # no key, provider not installed, daily cap: reported like any model failure
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": UNAVAILABLE}
