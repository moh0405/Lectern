"""Render evaluation results as Markdown."""

from __future__ import annotations

from typing import Any, Dict, List

from .metrics import KS


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def render_report(corpus_name: str, questions: List[Dict[str, Any]], runs: List[Dict[str, Any]], skipped: List[str]) -> str:
    qs = {q["id"]: q for q in questions}
    lines: List[str] = [f"# Retrieval evaluation: {corpus_name} corpus", ""]
    if runs:
        s0 = runs[0]["summary"]
        lines += [
            f"{s0.n_answerable} answerable questions and {s0.n_unanswerable} unanswerable ones. A retrieved passage counts as "
            "relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth "
            "does not depend on chunk boundaries.",
            "",
            "- **hit@k**: share of answerable questions with a relevant passage in the top k.",
            "- **MRR**: mean of 1 / rank of the first relevant passage.",
            "- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).",
            "- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions "
            "(1.0 perfect, 0.5 no better than chance). This is what a \"no good match found\" threshold would rely on.",
            "",
            "## Summary",
            "",
            "| config | setup | chunks | " + " | ".join(f"hit@{k}" for k in KS) + " | MRR | cov@5 | AUROC | ms/query |",
            "|---|---|---:|" + "---:|" * (len(KS) + 4),
        ]
        for r in runs:
            s = r["summary"]
            auc = "n/a" if s.abstain_auroc is None else f"{s.abstain_auroc:.2f}"
            lines.append(
                f"| **{r['config'].name}** | {r['config'].describe()} | {r['chunks']} | "
                + " | ".join(pct(s.hit[k]) for k in KS)
                + f" | {s.mrr:.3f} | {pct(s.coverage_at_5)} | {auc} | {r['query_ms']:.1f} |"
            )
        lines += ["", "## hit@3 by question type", ""]
        cats = sorted({c for r in runs for c in r["summary"].by_category})
        lines += ["| config | " + " | ".join(f"{c} (n={int(runs[0]['summary'].by_category[c]['n'])})" for c in cats) + " |",
                  "|---|" + "---:|" * len(cats)]
        for r in runs:
            lines.append(f"| **{r['config'].name}** | " + " | ".join(pct(r["summary"].by_category[c]["hit@3"]) for c in cats) + " |")

        lines += ["", "## Questions with no relevant passage in the top 5", ""]
        any_miss = False
        for r in runs:
            if not r["summary"].misses:
                continue
            any_miss = True
            lines.append(f"**{r['config'].name}** ({len(r['summary'].misses)}):")
            for qid in r["summary"].misses:
                q = qs[qid]
                res = next(x for x in r["results"] if x.id == qid)
                got = ", ".join(f"{d['doc']} ({d['score']})" for d in res.retrieved[:3]) or "nothing"
                lines.append(f"- `{qid}` [{q['category']}] {q['question']} → got {got}")
            lines.append("")
        if not any_miss:
            lines += ["No misses.", ""]

        lines += ["## Unanswerable questions: top score", "",
                  "| question | " + " | ".join(r["config"].name for r in runs) + " |", "|---|" + "---:|" * len(runs)]
        for q in questions:
            if q["answerable"]:
                continue
            row = []
            for r in runs:
                res = next(x for x in r["results"] if x.id == q["id"])
                row.append(f"{res.top_score:.2f}")
            lines.append(f"| {q['question']} | " + " | ".join(row) + " |")
        answerable_med = {}
        for r in runs:
            scores = sorted(x.top_score for x in r["results"] if x.answerable)
            answerable_med[r["config"].name] = scores[len(scores) // 2] if scores else 0.0
        lines.append("| *median of answerable questions* | " + " | ".join(f"{answerable_med[r['config'].name]:.2f}" for r in runs) + " |")
    if skipped:
        lines += ["", f"Skipped (dependency not installed): {', '.join(skipped)}."]
    return "\n".join(lines) + "\n"
