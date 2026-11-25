"""Offline evaluation of Try first feedback (`backend/attempt_feedback.py`) on a small labelled set of attempts.

`eval/attempts.jsonl` holds 15 student attempts over the synthetic corpus, 10 of them with deliberately wrong steps.
Each names the corpus sections it is judged against (so retrieval is not part of this test), the hidden answer key,
and the expected verdict for the units that make a judgeable claim.

    python -m eval.attempt_eval                        # scripted baseline judge, no model, no key (what CI runs)
    python -m eval.attempt_eval --outputs FILE         # re-score saved model replies, offline
    python -m eval.attempt_eval --live --save FILE     # call the configured model once per attempt (15 calls; never in CI)
    python -m eval.attempt_eval --write                # also write eval/reports/attempts.md
    python -m eval.attempt_eval --set leetcode [--live]  # the LeetCode set, judged with `judge="problem"` (8 calls if live)

`eval/leetcode_attempts.jsonl` holds correct, wrong and partial LeetCode attempts whose statement describes no method.
The model is only called with `--live`; the scripted baseline cannot reason, so its numbers on this set are only a floor.

Every reply, whatever its source, goes through the production code path (`interpret`): citation checks, the
unchecked label and the answer-leak guard. Metrics:

- verdict accuracy: the verdict as the student sees it equals the expected one, over labelled units (a verdict
  without a verified citation is shown as "unchecked", which never matches)
- wrong steps flagged (recall of `contradicted`) and how many flags were right (precision)
- false confidence: a wrong step shown as a *checked* "supported", the error the design most wants to avoid
- attempts with a wrong step where at least one wrong step was flagged
- citations verified, and notes or summaries that still restate the answer key after the guard
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.attempt_feedback import build_prompt, interpret, leaked, split_units

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "attempts.jsonl"
LEETCODE_DATA = ROOT / "leetcode_attempts.jsonl"
REPORT = ROOT / "reports" / "attempts.md"
LEETCODE_REPORT = ROOT / "reports" / "leetcode_attempts.md"

Reply = Callable[[Dict[str, Any], str], str]  # (attempt case, prompt) -> raw model text


def load(path: Path = DATA) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def section(doc: str, heading: str) -> str:
    text = (ROOT / "corpus" / doc).read_text()
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        raise KeyError(f"{doc} has no section {heading!r}")
    return " ".join(m.group(1).split())


def passages(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Corpus sections as passages. Markdown has no pages, so the label is the document name, as in the app."""
    statement = [{"doc": case["doc"], "page": None, "text": case["statement"], "score": 1.0}] if case.get("statement") else []
    return statement + [{"doc": doc, "page": None, "text": section(doc, heading), "score": 1.0} for doc, heading in case["passages"]]


def shown(item: Optional[Dict[str, Any]]) -> str:
    """The verdict the student sees: an uncited or unverified supported/contradicted is shown as unchecked."""
    if item is None:
        return "missing"
    if item.get("basis") == "problem":  # labelled as reasoned from the problem, so its verdict is what the student reads
        return item["verdict"]
    if item["verdict"] != "not_covered" and not item["checked"]:
        return "unchecked"
    return item["verdict"]


def score_case(case: Dict[str, Any], raw: str) -> Dict[str, Any]:
    chunks = passages(case)
    units = split_units(case["attempt"], case["format"])
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1])
    except ValueError:
        data = {}
    fb = interpret(data if isinstance(data, dict) else {}, case["question"], case["attempt"], units, case["format"], chunks, case.get("judge", "sources"))
    by_unit = {i["unit"]: i for i in fb["items"]}
    rows = [{"unit": int(u), "expected": v, "shown": shown(by_unit.get(int(u)))} for u, v in case["expected"].items()]
    cites = [c for i in fb["items"] for c in i["citations"]]
    leaks, _ = leaked(fb, case["answer_key"], case["question"], case["attempt"])
    return {"id": case["id"], "rows": rows, "citations": len(cites), "verified": sum(c["status"] == "ok" for c in cites),
            "leaks": leaks, "withheld": fb["withheld"], "readable": bool(data)}


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [r for res in results for r in res["rows"]]
    wrong = [r for r in rows if r["expected"] == "contradicted"]
    flagged = [r for r in rows if r["shown"] == "contradicted"]
    with_wrong = [res for res in results if any(r["expected"] == "contradicted" for r in res["rows"])]
    cites = sum(res["citations"] for res in results)
    return {
        "attempts": len(results),
        "units": len(rows),
        "accuracy": sum(r["shown"] == r["expected"] for r in rows) / max(len(rows), 1),
        "wrong_units": len(wrong),
        "wrong_flagged": sum(r["shown"] == "contradicted" for r in wrong) / max(len(wrong), 1),
        "flag_precision": sum(r["expected"] == "contradicted" for r in flagged) / max(len(flagged), 1) if flagged else None,
        "false_confidence": sum(r["shown"] == "supported" for r in wrong),
        "attempts_caught": sum(any(r["expected"] == r["shown"] == "contradicted" for r in res["rows"]) for res in with_wrong),
        "attempts_with_wrong": len(with_wrong),
        "unchecked": sum(r["shown"] == "unchecked" for r in rows),
        "citations_verified": (sum(res["verified"] for res in results) / cites) if cites else None,
        "leaks": sum(res["leaks"] for res in results),
        "withheld": sum(res["withheld"] for res in results),
        "unreadable": sum(not res["readable"] for res in results),
    }


def run(reply: Reply, cases: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    cases = cases or load()
    results, raws = [], {}
    for case in cases:
        units = split_units(case["attempt"], case["format"])
        prompt = build_prompt(case["question"], units, case["format"], passages(case), case.get("language"), case.get("judge", "sources"))
        raw = reply(case, prompt)
        raws[case["id"]] = raw
        results.append(score_case(case, raw))
    return {"summary": summarize(results), "results": results, "raw": raws}


def baseline_reply(_case: Dict[str, Any], prompt: str) -> str:
    """The deterministic word-overlap judge the tests and e2e server use. A floor to compare models against, not a tutor."""
    from tests.fake_gemini import scripted_attempt_feedback

    return json.dumps(scripted_attempt_feedback(prompt))


def live_reply(_case: Dict[str, Any], prompt: str) -> str:
    from backend.llm_providers import create_llm

    resp = create_llm(temperature=0.2).generate(prompt, json_mode=True)
    return resp.get("answer") or "" if resp.get("ok") else ""


def pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def report(name: str, s: Dict[str, Any], results: List[Dict[str, Any]]) -> str:
    lines = [
        f"# Try first feedback: {name}",
        "",
        f"{s['attempts']} attempts, {s['units']} labelled units, {s['wrong_units']} of them deliberately wrong "
        f"(in {s['attempts_with_wrong']} attempts). Generated by `python -m eval.attempt_eval`.",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| verdict accuracy (as shown to the student) | {pct(s['accuracy'])} |",
        f"| wrong steps flagged as contradicted | {pct(s['wrong_flagged'])} |",
        f"| flags that were right | {pct(s['flag_precision'])} |",
        f"| attempts with a wrong step where one was flagged | {s['attempts_caught']} / {s['attempts_with_wrong']} |",
        f"| wrong steps shown as checked \"supported\" (false confidence) | {s['false_confidence']} |",
        f"| verdicts shown as not checked against your sources | {s['unchecked']} |",
        f"| citations verified | {pct(s['citations_verified'])} |",
        f"| notes still restating the answer key | {s['leaks']} (replaced by the guard: {s['withheld']}) |",
        f"| unreadable replies | {s['unreadable']} |",
        "",
        "| attempt | expected → shown |",
        "|---|---|",
    ]
    for res in results:
        cells = ", ".join(f"{r['unit']}: {r['expected']}" + ("" if r["shown"] == r["expected"] else f" → **{r['shown']}**") for r in res["rows"])
        lines.append(f"| {res['id']} | {cells} |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--outputs", type=Path, help="JSON file {attempt id: raw model reply} to re-score offline")
    src.add_argument("--live", action="store_true", help="call the configured model (one call per attempt; needs a key)")
    ap.add_argument("--set", dest="dataset", choices=("attempts", "leetcode"), default="attempts", help="which labelled set to score")
    ap.add_argument("--save", type=Path, help="save the raw replies here (for --outputs later)")
    ap.add_argument("--write", action="store_true", help=f"write {REPORT.relative_to(ROOT.parent)}")
    args = ap.parse_args(argv)
    cases = load(LEETCODE_DATA if args.dataset == "leetcode" else DATA)
    target = LEETCODE_REPORT if args.dataset == "leetcode" else REPORT
    if args.outputs:
        saved = json.loads(args.outputs.read_text())
        out, name = run(lambda case, _p: saved.get(case["id"], ""), cases), f"saved replies ({args.outputs.name})"
    elif args.live:
        out, name = run(live_reply, cases), "live model"
    else:
        out, name = run(baseline_reply, cases), "scripted baseline (word overlap, no model)"
    if args.save:
        args.save.write_text(json.dumps(out["raw"], indent=1))
    text = report(name, out["summary"], out["results"])
    print(text)
    if args.write:
        target.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
