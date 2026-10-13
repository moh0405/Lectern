# Phase 0: Repo hygiene

## Where it started

A hackathon prototype: a Streamlit UI, a Python `RAGEngine` with FAISS and pickled metadata, Gemini for answers, extra features (LeetCode, concept maps, 3D view, analytics) bolted on in two weeks. It worked on one laptop. It had no tests, no CI, an incomplete dependency list, tracked `.DS_Store` files and copyrighted textbook PDFs, unused LangChain/Ollama code, and `eval`-based maths.

## Goal

Make a fresh clone install and pass CI with one command, so that everything after it can be changed safely.

## What was built

- `pyproject.toml` with optional **extras** (`embeddings`, `api`, `sources`, `leetcode`, `math`, `export`, `faiss`, `dev`). Installing the core stays light; heavy parts are opt-in.
- Removed dead code (LangChain, the Ollama client) and stopped tracking PDFs, `.DS_Store` and generated data. The PDFs are copyrighted textbooks supplied by the user and are not redistributed; `data/README.md` explains.
- `ruff` (lint), `mypy` (types, lenient to start), `pytest` (smoke tests), `pre-commit`, a `Makefile`.
- **GitHub Actions** CI on Python 3.10 and 3.12.
- Made the Kaggle import lazy and `SystemExit`-safe (importing the module used to crash the process when no Kaggle credentials existed).

## Technologies (see concepts)

| Tool | Role |
|---|---|
| `pyproject.toml` extras | dependency groups ([backend](../concepts/07-backend-stack.md)) |
| ruff | fast Python linter |
| pytest | tests ([testing](../concepts/10-testing-and-ci.md)) |
| GitHub Actions | CI |
| pre-commit | run checks before each commit |

## Decisions

- **Lower-bounded versions, not pinned.** A lockfile comes with deployment (Phase 6).
- **History was not rewritten** to remove PDFs, just stop tracking them: rewriting shared history is destructive for little benefit here.
- **mypy non-blocking** at first, so type cleanup does not hold everything else up.

## Bugs found

- Importing a module could kill the process (`SystemExit` from Kaggle).
- A shadowed import in the old app, found by ruff.

## Result

One command (`pip install -e ".[all]"`) installs; CI runs lint and tests on two Python versions.

## What you learn from this phase

Engineering hygiene is what makes later speed possible: when 270 tests and a CI gate exist, a refactor of the core search is a normal afternoon, not a risk.
