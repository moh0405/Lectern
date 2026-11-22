"""Feedback on a student's own attempt ("Try first"), judged against the retrieved passages.

The attempt is split into units the feedback can point at: steps (one per line), code lines, or the sentences of a
short answer. One model call judges each unit as `supported`, `contradicted` or `not_covered` by the passages and
cites the passage it relied on. Citations are checked exactly as Ask checks them (`backend/citations.py`), and a
verdict without a verified citation is reported as unchecked (`checked: false`), because a wrong "supported" is worse
than no verdict at all.

The feedback must never hand over the solution: the prompt asks for pointers only, and the model also writes a
one-sentence `answer_key` (never returned) so that a note or summary that restates it can be replaced by a neutral
pointer (`hint_leaks_answer`, the same guard the Socratic hints use). Code blocks are removed from notes too.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .advanced_ai import hint_leaks_answer
from .citations import Citation, check_answer, extract_citations
from .llm_providers import create_llm
from .rag_engine import RAGEngine

logger = logging.getLogger("ai-study-mentor.attempt")

FORMATS = ("steps", "code", "short_answer")
VERDICTS = ("supported", "contradicted", "not_covered")
MAX_UNITS = {"steps": 30, "code": 200, "short_answer": 30}
UNIT_NAME = {"steps": "Step", "code": "Line", "short_answer": "Sentence"}
PASSAGE_CHARS = 900
NOTE_CHARS = 400
SUMMARY_CHARS = 600

_NUMBERING = re.compile(r"^\s*(?:(?:step|line)\s*)?\(?\d{1,3}\s*[.):\-]\s+", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'`])")
_FENCE = re.compile(r"```[\s\S]*?(?:```|$)")

FALLBACK_NOTE = {
    "supported": "Your sources back this. Open the cited passage to see where.",
    "contradicted": "This does not match the cited passage. Re-read it and compare it with what you wrote.",
    "not_covered": "Your sources do not cover this, so it could not be checked here.",
}
FALLBACK_SUMMARY = ("Compare the flagged parts of your attempt with the cited passages. When you want the full answer, "
                    "choose Show me the evidence.")

RUBRIC = {
    "steps": ("a problem worked step by step. Each STEP is one line of the student's working. Judge whether each step "
              "is a correct move according to the PASSAGES, including any number or result it states."),
    "code": ("a program{language}. Each LINE is numbered as in the student's editor. Judge the lines that carry logic "
             "(conditions, updates, loop bounds, return values, complexity claims in comments) against what the PASSAGES "
             "describe; skip blank lines, braces and imports. Judge behaviour, not style."),
    "short_answer": ("a short written answer. Each SENTENCE is one claim. Judge whether each claim agrees with the "
                     "PASSAGES."),
}

PROMPT = """TASK: ATTEMPT_FEEDBACK
You are a tutor checking a student's own attempt before they see any answer. The attempt is {rubric}

Judge each numbered unit of the ATTEMPT against the PASSAGES only:
- "supported": a passage states or directly implies it. Cite that passage.
- "contradicted": a passage says something that makes it wrong. Cite that passage.
- "not_covered": the passages do not address it. Do not judge it from general knowledge, and give no citation.

Cite with the label exactly as it appears in square brackets before a passage, for example "notes.pdf (page 4)".
Never cite anything that is not listed in PASSAGES.

The student has not seen the answer and must still work it out. So:
- Never write the correct solution, the corrected step, the final answer or a fixed line of code.
- For a contradicted unit, say what to re-check and where ("Compare this with what heaps.pdf (page 2) says about ..."),
  not what the right version is.
- Each "note" is one or two sentences, a pointer or a question, not an explanation of the answer.
- The "summary" is one or two sentences: what is on track and which unit to look at first. No solution.

Also write "answer_key": the correct answer in one sentence. It is only used to check that your feedback does not give
it away and is never shown.

Return pure JSON:
{{"answer_key": "...", "summary": "...", "items": [{{"unit": 1, "verdict": "supported", "note": "...", "citations": ["doc (page N)"]}}]}}
Give at most one item per unit; "unit" is the number shown before it.

QUESTION: {question}

ATTEMPT ({unit_plural}):
{units}

PASSAGES:
{passages}"""


class AttemptTooLong(ValueError):
    """The attempt has more units than the feedback can judge."""


def split_units(attempt: str, fmt: str) -> List[str]:
    """The units feedback can point at. Steps: non-empty lines without their own numbering. Code: every line (blank
    lines kept, so numbers match the editor; trailing blanks dropped). Short answer: sentences."""
    text = (attempt or "").replace("\r\n", "\n").replace("\r", "\n")
    if fmt == "code":
        lines = [line.rstrip() for line in text.split("\n")]
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        units = lines
    elif fmt == "steps":
        units = [_NUMBERING.sub("", line).strip() for line in text.split("\n")]
        units = [u for u in units if u]
    else:
        units = [s.strip() for para in text.split("\n") for s in _SENTENCE.split(para) if s.strip()]
    if len(units) > MAX_UNITS[fmt]:
        raise AttemptTooLong(f"Keep the attempt to {MAX_UNITS[fmt]} {UNIT_NAME[fmt].lower()}s or fewer so each one can be checked.")
    return units


def _passages(chunks: Sequence[Dict[str, Any]]) -> str:
    return "\n".join(f"- [{RAGEngine.source_label(c)}] {(c.get('text') or '').strip()[:PASSAGE_CHARS]}" for c in chunks) or (
        "(none: nothing in the student's material matched, so every unit is not_covered)"
    )


def build_prompt(question: str, units: List[str], fmt: str, chunks: Sequence[Dict[str, Any]], language: Optional[str] = None) -> str:
    name = UNIT_NAME[fmt]
    numbered = "\n".join(f"{name} {i}: {u}" if u.strip() else f"{name} {i}:" for i, u in enumerate(units, 1))
    rubric = RUBRIC[fmt].replace("{language}", f" in {language}" if language else "")
    return PROMPT.format(rubric=rubric, question=question, unit_plural=f"{name.lower()}s", units=numbered, passages=_passages(chunks))


def _json(text: str) -> Dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def _check_item(note: str, labels: List[str], chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The item's citations, checked like Ask's: each listed label, plus any citation written into the note. A listed
    label that matches no passage is a source the model was not given (unknown_source)."""
    found: List[Dict[str, Any]] = []
    for raw in labels:
        label = str(raw).strip().strip("[]").strip()
        if not label:
            continue
        checked = extract_citations(f"[{label}]", chunks)
        found.append((checked[0] if checked else Citation(label=label, doc=label, page=None, status="unknown_source")).to_dict())
    found += check_answer(note, chunks)["citations"]
    unique, seen = [], set()
    for c in found:
        key = (c["label"].lower(), c["status"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _clean(text: Any, limit: int) -> str:
    out = _FENCE.sub("", str(text or "")).strip()
    return out[:limit].rstrip() + ("…" if len(out) > limit else "")


def interpret(data: Dict[str, Any], question: str, attempt: str, units: List[str], fmt: str,
              chunks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn the model's JSON into checked, guarded feedback."""
    answer_key = data.get("answer_key") if isinstance(data.get("answer_key"), str) else ""
    # Words the student already wrote are not a leak when the feedback repeats them.
    known = f"{question}\n{attempt}"
    withheld = 0
    items: List[Dict[str, Any]] = []
    seen_units = set()
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        try:
            unit = int(raw.get("unit"))
        except (TypeError, ValueError):
            continue
        if not 1 <= unit <= len(units) or unit in seen_units or not units[unit - 1].strip():
            continue
        verdict = str(raw.get("verdict") or "").strip().lower().replace(" ", "_").replace("-", "_")
        if verdict not in VERDICTS:
            continue
        seen_units.add(unit)
        note = _clean(raw.get("note"), NOTE_CHARS)
        labels = raw.get("citations") if isinstance(raw.get("citations"), list) else ([raw["citations"]] if isinstance(raw.get("citations"), str) else [])
        citations = [] if verdict == "not_covered" else _check_item(note, labels, chunks)
        if not note or hint_leaks_answer(note, answer_key, known):
            withheld += bool(note)
            note = FALLBACK_NOTE[verdict]
        checked = verdict != "not_covered" and any(c["status"] == "ok" for c in citations)
        items.append({"unit": unit, "ref": f"{UNIT_NAME[fmt]} {unit}", "verdict": verdict, "note": note,
                      "citations": citations, "checked": checked})
    items.sort(key=lambda i: i["unit"])
    summary = _clean(data.get("summary"), SUMMARY_CHARS)
    if not summary or hint_leaks_answer(summary, answer_key, known):
        withheld += bool(summary)
        summary = FALLBACK_SUMMARY
    if withheld:
        logger.info("Replaced %d feedback note(s) that gave the answer away", withheld)
    unverified = sum(1 for i in items for c in i["citations"] if c["status"] != "ok")
    return {"ok": True, "items": items, "summary": summary, "withheld": withheld, "unverified_citations": unverified}


def give_feedback(question: str, attempt: str, fmt: str, chunks: Sequence[Dict[str, Any]], language: Optional[str] = None,
                  model: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
    """Judge an attempt with one model call. Returns {"ok": False, "error"} when the model fails or its reply cannot be
    read (raises AttemptTooLong for an attempt that is too long to judge)."""
    units = split_units(attempt, fmt)
    if not units:
        raise AttemptTooLong("Write at least one step, line or sentence of your attempt.")
    chunks = [c for c in chunks if (c.get("text") or "").strip()]
    prompt = build_prompt(question, units, fmt, chunks, language)
    try:
        client = create_llm(model=model, temperature=temperature)
        resp = client.generate(prompt, json_mode=True)
    except Exception as e:  # no key, provider not installed, daily cap: reported like any model failure
        return {"ok": False, "error": str(e)}
    if not resp.get("ok"):
        return {"ok": False, "error": resp.get("error")}
    try:
        data = _json((resp.get("answer") or "").strip())
    except ValueError as e:
        logger.warning("Attempt feedback was not JSON (%s)", e)
        return {"ok": False, "error": "The model's feedback could not be read. Try again."}
    result = interpret(data, question, attempt, units, fmt, chunks)
    return {**result, "units": units, "model": resp.get("model"), "prompt": prompt}


def leaked(feedback: Dict[str, Any], answer_key: str, question: str, attempt: str) -> Tuple[int, List[str]]:
    """For the eval: notes and summary that restate `answer_key` beyond what the student wrote."""
    known = f"{question}\n{attempt}"
    texts = [i["note"] for i in feedback.get("items") or []] + [feedback.get("summary") or ""]
    bad = [t for t in texts if t and hint_leaks_answer(t, answer_key, known)]
    return len(bad), bad
