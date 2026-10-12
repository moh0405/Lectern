"""Run the retrieval evaluation and write a report.

    python -m eval.run                         # all configs on the synthetic corpus
    python -m eval.run --configs hashing-dense,keyword
    python -m eval.run --write                 # also update eval/reports/synthetic.md

Configs that need sentence-transformers are skipped (and listed) if it is not installed.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List

from .harness import CONFIGS, CORPORA, ROOT, evaluate, load_questions
from .report import render_report


def available(config) -> bool:
    if config.embedder.startswith("hashing-"):
        return True
    try:
        import sentence_transformers  # noqa: F401
    except Exception:
        return False
    return True


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", choices=[*CORPORA, "both"], default="synthetic")
    ap.add_argument("--configs", help="comma-separated config names (default: all)")
    ap.add_argument("--write", action="store_true", help="write eval/reports/<corpus>.md")
    args = ap.parse_args(argv)

    wanted = args.configs.split(",") if args.configs else list(CONFIGS)
    unknown = [w for w in wanted if w not in CONFIGS]
    if unknown:
        print(f"unknown configs: {unknown}. available: {list(CONFIGS)}", file=sys.stderr)
        return 2

    status = 0
    for cname in (list(CORPORA) if args.corpus == "both" else [args.corpus]):
        corpus = CORPORA[cname]
        why = corpus.available()
        if why:
            print(f"skipping the {cname} corpus: {why}", file=sys.stderr)
            status = status or (1 if args.corpus != "both" else 0)
            continue
        runs: List[Dict[str, Any]] = []
        skipped: List[str] = []
        for name in wanted:
            cfg = CONFIGS[name]
            if not available(cfg):
                skipped.append(name)
                continue
            print(f"[{cname}] running {name} ...", flush=True)
            runs.append(evaluate(corpus, cfg))
        report = render_report(cname, load_questions(corpus.questions), runs, skipped)
        print(report)
        if args.write:
            out = ROOT / "reports" / f"{cname}.md"
            out.write_text(report, encoding="utf-8")
            print(f"wrote {out}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
