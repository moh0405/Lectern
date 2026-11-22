"""Similar example: one new practice question on the same concept, written from the passages the student just read.

One model call, only when the student asks. The model also writes a one-sentence `answer_key`, which is never returned:
it is used to reject a question that gives its own answer away (`hint_leaks_answer`, the guard hints and feedback use).
A question is only returned when it cites a passage it was given and shares content with that passage, so it stays
grounded, and when it is not a rewording of the original question or of one already offered.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from .advanced_ai import _content_words, hint_leaks_answer
from .attempt_feedback import _check_item, _clean, _json, _passages
from .llm_providers import create_llm

logger = logging.getLogger("ai-study-mentor.similar")

MIN_CHARS = 12
MAX_CHARS = 500
MAX_OVERLAP = 0.8  # share of content words above which a question counts as a rewording
MIN_GROUNDING_WORDS = 2

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


def build_prompt(question: str, chunks: Sequence[Dict[str, Any]], previous: Sequence[str] = ()) -> str:
    asked = "\n".join(f"* {p}" for p in previous) or "(none)"
    return PROMPT.format(question=question, previous=asked, passages=_passages(chunks))


def _overlap(a: str, b: str) -> float:
    x, y = _content_words(a), _content_words(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def _grounded(text: str, citations: List[Dict[str, Any]], chunks: Sequence[Dict[str, Any]]) -> bool:
    """A verified citation whose passage shares real content with the question."""
    words = _content_words(text)
    docs = {c.get("doc") for c in citations if c["status"] == "ok"}
    return any(c.get("doc") in docs and len(words & _content_words(c.get("text") or "")) >= MIN_GROUNDING_WORDS for c in chunks)


def interpret(data: Dict[str, Any], question: str, chunks: Sequence[Dict[str, Any]], previous: Sequence[str] = ()) -> Optional[Dict[str, Any]]:
    """The checked practice question, or None when it fails a guard. The answer key never leaves this function."""
    text = _clean(data.get("question"), MAX_CHARS + 1)
    key = data.get("answer_key") if isinstance(data.get("answer_key"), str) else ""
    if not MIN_CHARS <= len(text) <= MAX_CHARS or not key.strip():
        return None
    if key.strip().lower() in text.lower() or hint_leaks_answer(text, key, question):
        logger.info("Rejected a practice question that gave its answer away")
        return None
    if any(_overlap(text, seen) >= MAX_OVERLAP for seen in [question, *previous]):
        return None
    raw = data.get("citations")
    labels = raw if isinstance(raw, list) else [raw] if isinstance(raw, str) else []
    citations = [c for c in _check_item("", labels, chunks) if c["status"] == "ok"]
    if not _grounded(text, citations, chunks):
        return None
    return {"question": text, "citations": citations}


def similar_question(question: str, chunks: Sequence[Dict[str, Any]], previous: Sequence[str] = (), model: Optional[str] = None,
                     temperature: float = 0.4) -> Dict[str, Any]:
    """Write one practice question with one model call. Returns {"ok": False, "error"} when none passes the guards."""
    chunks = [c for c in chunks if (c.get("text") or "").strip()]
    try:
        client = create_llm(model=model, temperature=temperature)
        resp = client.generate(build_prompt(question, chunks, previous), json_mode=True)
    except Exception as e:  # no key, provider not installed, daily cap: reported like any model failure
        return {"ok": False, "error": str(e)}
    if not resp.get("ok"):
        return {"ok": False, "error": resp.get("error")}
    try:
        data = _json((resp.get("answer") or "").strip())
    except ValueError as e:
        logger.warning("Similar question was not JSON (%s)", e)
        return {"ok": False, "error": UNAVAILABLE}
    result = interpret(data, question, chunks, previous)
    if result is None:
        return {"ok": False, "error": UNAVAILABLE}
    return {"ok": True, **result, "model": resp.get("model")}
