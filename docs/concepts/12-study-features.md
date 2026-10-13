# 12. Study features: spaced repetition, progress tracking, history, and LLM providers

Phase 5 added the parts that make the project a study *tool*, not only a question-answering demo.

## Spaced repetition and SM-2

**The idea.** You forget things on a curve: fast at first, then slowly. A review right before you would forget resets the curve and flattens it, so the next gap can be longer. Reviewing every card daily wastes time; reviewing too late means relearning. *Spaced repetition* schedules each card at the moment it is about to be forgotten.

**SM-2** (SuperMemo 2, 1987) is the simple algorithm behind Anki's classic scheduler. Each card has:

- `repetitions`: how many times in a row you have recalled it,
- `interval_days`: the current gap,
- `ef`, the **ease factor** (starts 2.5): how fast the gap grows for this card.

After a review graded 0 (blackout) to 5 (perfect):

| Grade | What happens |
|---|---|
| below 3 (a lapse) | `repetitions = 0`, `interval = 1 day`, `lapses += 1` |
| 3 or more, first time | interval 1 day |
| 3 or more, second time | interval 6 days |
| 3 or more, later | `interval = round(previous interval × ef)` |
| always | `ef += 0.1 - (5-g)(0.08 + (5-g)×0.02)`, never below 1.3 |

Worked example (from the tests): grade 4 three times in a row gives intervals **1, 6, 15 days** (15 = round(6 × 2.5); a grade of 4 leaves the ease factor unchanged). Grade 5 raises `ef` to 2.6; grade 3 lowers it to 2.36; repeated blackouts bottom out at 1.3.

The UI offers four buttons that send grades **Again = 1, Hard = 3, Good = 4, Easy = 5**. The implementation is `backend/srs.py`: a pure function (state and grade in, new state out), no clock and no database, which is why it is thoroughly unit-tested. `backend/api/study_store.py` applies it and stores the due time.

**Where cards come from.** Typed by hand; saved from any Ask answer (one click); or written by the model (`POST /cards/generate`): it receives passages from your material and a prompt asking for JSON cards. The reply is parsed *tolerantly* (`backend/flashcards.py`): prose around the JSON is ignored, a bare list is accepted as well as `{"cards": [...]}`, entries missing a side or with duplicate fronts are dropped, and a reply with no usable cards is an error instead of an empty success. A test caught a real bug here: parsing a bare list first grabbed the inner `{...}` object.

**Export.** CSV (`front,back`) imports into Anki directly. The real Anki package (`.apkg`) uses `genanki`, an optional extra, with fixed note-type and deck ids and content-derived note ids so importing twice updates rather than duplicates.

## LeetCode progress and the study plan

Each problem can be *to do*, *attempted* or *solved*, with notes. The plan (`backend/study_plan.py`, a pure function) counts attempted and solved problems per topic; a topic is **weak** when you tried some of it and solved under half of what you tried. It then lists unsolved problems from the weakest topics first, easiest first (so a session starts with something winnable), and with no history suggests easy problems to begin with. It is deliberately simple and explainable: every item says why it is there ("Weak topic: Dynamic Programming").

## History without accounts

Finished Ask turns are saved to the server as well as the browser (`POST /history`), and restored if the browser has none (for example after clearing site data). Server calls are best-effort: if the API is unreachable, Ask keeps working from local storage. Deleting a turn deletes it on the server too, otherwise a cleared history would reappear on the next load. Restored turns are marked as already synced so they are not saved twice.

**Why no accounts?** This is a personal tool, and a login system (password storage, sessions, per-user data isolation, abuse handling) is a large security surface that adds little to what the project demonstrates. Everything is in one SQLite file (`STUDY_DB`). Multi-user support would be its own phase, with a real database.

## One interface for several language models

`backend/llm_providers.py` defines what the app needs from a model: `generate`, `stream`, `list_supported_models` and a `model` name (a `typing.Protocol`, so any class with those members qualifies). `create_llm()` returns the provider chosen by `LLM_PROVIDER`:

| Provider | Class | Notes |
|---|---|---|
| `gemini` (default) | `GeminiClient` | `google-genai` SDK, model resolution and fallback |
| `openai` | `OpenAICompatClient` | chat-completions API; with `OPENAI_BASE_URL` it also talks to Ollama, vLLM, LM Studio, OpenRouter and similar |

Both normalise to the same results (`{"ok": True, "model", "answer"}` or `{"ok": False, "error"}`), retry transient errors, stream text pieces, and support JSON mode (Gemini's response MIME type, OpenAI's `response_format`). Call sites no longer name a provider; they call `create_llm(...)`. That also made tests simpler: one name to replace with a fake.

**Honesty note:** the OpenAI-compatible client is tested against fake SDK clients, not against a live server, because no key was available while building it. Prompts were written and measured with Gemini; another model may follow the citation format or JSON instructions less reliably.

## Where to look

`backend/srs.py`, `backend/flashcards.py`, `backend/study_plan.py`, `backend/api/study_store.py`, `backend/api/routers/tracking.py`, `backend/llm_providers.py`; frontend `apps/web/features/study/`, `features/leetcode/progress.tsx` and `study-plan.tsx`, `features/ask/use-ask-session.ts`.
