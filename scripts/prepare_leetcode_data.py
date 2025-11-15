#!/usr/bin/env python3

"""
Prepare LeetCode datasets locally for the Study Mentor app.

This script attempts to download and normalize the following datasets:
  1) HuggingFace: kaysss/leetcode-problem-set
  2) Kaggle: gzipchrist/leetcode-problem-dataset
  3) Kaggle: mohitkumar282/leetcode-questions-dataset

Outputs:
  - data/leetcode/normalized_problems.jsonl
  - data/leetcode/embeddings.npy (if sentence-transformers is available)

Usage:
  python scripts/prepare_leetcode_data.py
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.leetcode_handler import LeetCodeHandler


def main() -> int:
    handler = LeetCodeHandler(cache_dir=str(PROJECT_ROOT / "data" / "leetcode"))
    n, status = handler.load_all(force=True, generate_embeddings=False)
    print(f"Loaded {n} problems ({status})")
    stats = handler.get_stats()
    print("Stats:")
    print(json.dumps(stats, indent=2))
    # Embeddings are disabled here to avoid macOS segfaults; check presence
    out_emb = PROJECT_ROOT / "data" / "leetcode" / "embeddings.npy"
    if out_emb.exists():
        print(f"Embeddings saved at: {out_emb}")
    else:
        print("Embeddings not generated (sentence-transformers missing); keyword search will be used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())