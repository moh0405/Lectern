# Phase 5: Study tools

## Goal

Turn a question-answering system into something you could use to study for weeks: remember what you were shown, schedule reviews, track progress, and not depend on a single model vendor.

## What was built

1. **Provider interface for language models** (`backend/llm_providers.py`): Gemini or any OpenAI-compatible server, chosen by `LLM_PROVIDER`. Call sites changed from `GeminiClient(...)` to `create_llm(...)`.
2. **Flashcards with SM-2 spaced repetition** (`backend/srs.py`): cards added by hand, saved from an answer, or written by the model from your material; a review page; CSV and Anki (`.apkg`) export.
3. **LeetCode progress and study plan** (`backend/study_plan.py`): todo / attempted / solved with notes, shown in the list; a plan from weak topics.
4. **Server-side history**: finished Ask turns saved on the server and restored when the browser has none.
5. **A new SQLite store** (`backend/api/study_store.py`, `data/study.db`) for cards, progress and history.
6. **14 new API operations** (40 total), a Flashcards page, and changes to Ask and LeetCode.

How each works, with the SM-2 numbers: [concepts/12-study-features.md](../concepts/12-study-features.md).

## Decisions

| Decision | Reason |
|---|---|
| **No accounts**, one SQLite file | Personal tool; auth is a large security surface that adds little here. Stated up front and recorded in `docs/PLAN.md`. |
| Pure functions for SM-2 and the plan | No clock or database inside, so they are trivially testable |
| Anki: CSV always, `.apkg` as an optional extra | `genanki` was not a dependency (the plan said it was); keep the base install light |
| Provider as a `Protocol` plus a factory | Tests replace one name; adding a provider means one class |
| History sync is best-effort, deletes mirrored | An unreachable server must not break Ask; a local delete must not be undone by a restore |
| Plan is a transparent heuristic | "Under half solved" is explainable on screen; a smarter model would not be |

## Bugs found by the tests

- The flashcard JSON parser took the inner `{...}` of a bare list first and returned nothing; a test with a bare list caught it.
- E2E tests leaked Ask history into each other once history lived on the server; a shared fixture now empties it before each test.
- The "no key" messages named only Gemini, which was wrong once there were two providers.

## Testing

318 backend tests (SM-2 properties, plan, store, flashcard parsing and export, every new route, provider behaviour with fake SDK clients), 71 frontend tests, and browser tests for the review flow, generation, export, save-from-answer, history restore, LeetCode progress and plan, plus an accessibility scan of the new page.

## Not done, and said plainly

- The OpenAI-compatible provider has **not been run against a live endpoint**.
- Multi-user accounts, sync across devices, and a per-card history chart.
- The SM-2 interval preview on the buttons ("Good: 6 days") was left out so the scheduling rule lives in one place (the server).
