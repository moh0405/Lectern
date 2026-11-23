# Evidence Desk: implementation plan

Status: **Phases 0–1 implemented** on branch `moh0405/evidence-desk` (direction decided 21 November 2026). Phases 2–7 not started.
Prototype: [`design-options/`](design-options/README.md), concept A (`?concept=a&state=answer`).
Background: [`HANDOFF.md`](../../HANDOFF.md).

## 1. Goal

Replace the rejected deployed layout with **Evidence Desk**: a full-width workspace with the library on the left, the question and answer in the middle, and a warm "paper" source margin on the right that shows the passage each citation points to.

Evidence Desk becomes a learning loop instead of a single answer box:

```
Question ─────────► Evidence ─────────────────► Understanding
your question       hints in stages (optional)   your own words
+ optional attempt  answer with citations        similar example
                    source margin                save as flashcard
                    feedback on your attempt
```

What should set Lectern apart: **every claim can be traced to a passage you can read, and the tutor can make you think before it tells you.**

## 2. What we take from Askretes

[Askretes](https://askretes.us/) ("The AI tutor your professor approves of") is an attempt-first tutor. Students open a class assignment, write an attempt, and only then ask; it says plainly that it "will not give you the answer". Reviewed 18–21 November 2026 from its public page and interface text.

| Askretes idea | Take it? | How it lands in Lectern |
| --- | --- | --- |
| Attempt first: "Write your own attempt, then ask" | **Yes, as an option** | A *Try first* toggle in the composer. Lectern stays a reference tutor, so this never blocks an answer. |
| Won't give the answer | **Partly** | *Guided* mode: hints in stages first, then "Show me the evidence" reveals the full cited answer. |
| "Write what you understand so far" | **Yes** | Placeholder copy for the attempt box, and the prompt in the Understanding step. |
| "Show your working, one step per line" | **Yes** | A step-per-line attempt format for problems, so feedback can point at a single step. |
| Assignment types: "A problem worked to a final answer", "A program to write", "A short answer or a paragraph" | **Yes, lightly** | An attempt *format* picker (Steps / Code / Short answer) that changes the input box and the feedback rubric. |
| "Material to learn. No answer key. Askretes teaches it." | **Already ours** | This is what Lectern's retrieval over your own documents already does. Make it explicit in the Library copy. |
| "Similar example" | **Yes** | A button in Understanding that generates a new practice question on the same idea from the same sources. |
| Classes with professors, students and due dates | **No** | Lectern is single-user with no accounts by design ([PLAN.md](../PLAN.md), Phase 5). A lightweight local *study set* is listed as optional (Phase 7). |
| "The AI tutor your professor approves of" | **Adapt the idea** | Integrity is part of the pitch. Lectern's version: "An AI tutor that shows its sources." |
| Stock HeroUI look | **No** | Evidence Desk is already more distinctive. |

Lectern's advantage over Askretes is grounding: feedback on an attempt can cite the exact passages that confirm or contradict each step, and reuse the existing citation checks (`CitationCheck`: `ok`, `page_not_retrieved`, `unknown_source`).

## 3. What already exists (reuse, don't rebuild)

| Need | Existing piece |
| --- | --- |
| Streamed answers with cancel | `POST /ask/stream` (SSE `meta`/`token`/`done`/`error`), `features/ask/use-ask-session.ts` |
| Retrieved passages and citation checks | `AskResponse.chunks` (`Chunk`: text, doc, page, end_page, score, url, citation_url), `citations`, `unverified_citations`, `uncited` |
| Answers from browser-local documents (demo) | `AskRequest.context` + browser RAG (`features/sources`) |
| Hint ladder | `POST /socratic` → `Socratic{questions, hints}` (`backend/advanced_ai.py:104`), already allowed in demo by `lib/backend-proxy.ts` |
| Explain at a level with a mini quiz | `POST /adaptive` |
| Flashcards with SM-2 | `/cards`, `/cards/generate`, browser-local cards in demo (`features/ask/flashcards.ts`) |
| Notes from a session | `POST /notes`, `features/ask/notes-panel.tsx` |
| Saved turns | `/history` |
| Agentic Ask | `POST /ask/agent/stream` |
| Test model | `tests/fake_gemini.py` (scripted, also covers tool calling) |

The behaviour fixes from the rejected refresh (`9b95dc4`, `8ee7cd9`) stay: reading themes (`lectern-reading-theme` key), 44px controls, capacity/busy handling, metadata cache, clipboard errors, LeetCode overflow fix, Plotly theming.

## 4. Phases

Each phase ends with passing checks and is its own PR. Phases 1–2 deliver the redesign; 3–5 add the Askretes-inspired learning loop.

### Phase 0: Design foundations
- Move the prototype's tokens into `app/globals.css`: dark workspace palette, warm paper palette for the source margin, purple accent, light theme counterparts.
- Fonts: Manrope 400/600 and IBM Plex Mono 400 (OFL, already in `design-options/fonts/`) via `next/font/local`, plus the serif for source passages.
- Shared primitives in `components/ui/`: citation chip, step tabs, paper panel, mono eyebrow label.
- Read `apps/web/AGENTS.md` and `node_modules/next/dist/docs/` first (Next 16.4).

**Done when:** tokens and primitives exist, both themes pass contrast checks, no page changes yet.

*Built:* tokens in `app/globals.css` (dark desk, warm paper, light theme), Manrope/Plex Mono via `next/font/local` (`app/fonts/`), Georgia for passages; shared `.eyebrow`, `.paper`, `.cite-chip` classes. Primary buttons now use dark text on the lighter accent (`--color-accent-fg`).

### Phase 1: Evidence Desk shell and Ask page (the redesign)
- **Shell (`components/app-shell.tsx`):** top bar with Lectern mark, primary nav **Ask / Library / Practice / Tools**, command search (Ctrl/Cmd+K), theme toggle. Existing routes stay reachable: Library = Sources; Practice = Study + LeetCode; Tools = Tutor, Math, Visualize, Agent, Analytics.
- **Left rail:** "Your library" (server textbook index + browser-local documents) and recent questions from history/session.
- **Middle column:** eyebrow, large question heading, streamed answer split into paragraphs, **citation chips** (`01`, `02` …) built from `citations`. Chip state follows `CitationCheck.status`: `ok` normal; `page_not_retrieved` and `unknown_source` marked with a warning and never linked to a fake passage.
- **Right source margin:** the chunk for the selected citation, with doc, page range and `citation_url` deep link. Highlight the sentence in the chunk that best matches the citing sentence (client-side token overlap, labelled "closest match"); "Read a little more context" expands the full chunk; "Open the complete document" when a URL exists.
- **Connector line** from the active chip to the margin: desktop only, off for reduced motion, toggled by "Trace on/off".
- **Step tabs** Question / Evidence / Understanding (Understanding is a stub until Phase 4).
- **Composer** at the bottom: follow-up input, source picker, Advanced (model, k, mode, agentic), Ctrl/Cmd+Enter.
- **Phone:** stack question → answer → sources; the margin becomes a sheet opened from a chip.
- **Never** show the prototype's illustrative collision content; the empty state is real suggestions from `/suggestions`.

**Done when:** Ask matches the refined prototype at 1440/768/390/320 in both themes with real streamed data; cancel, retry, busy (429) and citation warnings work; demo mode works with browser-local documents; e2e and visual suites updated.

*Built, with two differences from the outline above:*
- Below 1180px the columns stack (answer, then source margin, then library) instead of opening the margin as a sheet. This matches the prototype's phone layout and keeps every passage reachable without a dialog.
- The Understanding step uses what already exists (study notes and export, links to flashcards and the Socratic tutor) rather than a stub. Phase 4 replaces it.
- Code: `components/app-shell.tsx`, `lib/sections.ts`, `features/ask/{ask-view,turn-card,source-margin,trace-line,citations}.tsx?`, `features/ask/ask.module.css`.

### Phase 2: Guided mode (hints before the answer)
- Composer toggle: **Answer** (default) / **Guided**.
- Guided calls `POST /socratic` with the same retrieved context and shows hint 1. Buttons: "Next hint" (2, then 3), "Show me the evidence" (runs the normal cited answer).
- Hints sit in the Evidence step above the answer; the answer reveals into the existing layout.
- Each hint request counts against `DAILY_LLM_LIMIT`; reuse fetched hints instead of refetching.

**Done when:** Guided works in private and demo modes, is keyboard accessible, and has unit + e2e tests with FakeGemini.

### Phase 3: Try first (attempt and grounded feedback)
- Composer toggle **Try first**. Opens an attempt box ("Write what you understand so far") with a format picker:
  - **Steps:** one step per line, numbered ("Show your working, one step per line").
  - **Code:** monospace editor, language label.
  - **Short answer:** plain paragraph.
- **New endpoint `POST /attempt/feedback`** (JSON, not streamed, to start):
  - Request: `question`, `attempt`, `format`, `k`, optional `context` (browser-local passages, as in `AskRequest`), optional `model`.
  - Server retrieves passages, asks the model to judge each step/claim against them, and returns:
    `items: [{ref: "step 2", verdict: "supported" | "contradicted" | "not_covered", note, citations: [CitationCheck]}]`, `summary`, `chunks`, `model`.
  - Same citation verification as Ask; uncited verdicts are labelled "not checked against your sources".
  - Must not hand back a full solution: the prompt gives feedback and pointers, and "Show me the evidence" is how the student asks for the answer.
- In the UI, each attempt line gets a verdict marker; clicking a verdict opens its passage in the source margin.
- Backend: schema + router + prompt in `backend/`; tests with `FakeGemini`; add `attempt/feedback` to the demo allow-list in `lib/backend-proxy.ts`; run `python scripts/export_openapi.py` and `npm run client:generate` and commit both.
- Eval: add a small set (about 15 attempts, some deliberately wrong) to `eval/` and report verdict accuracy, measured offline. It is not run in CI against a paid model.

**Done when:** feedback is grounded and cited, wrong steps are flagged in the eval set, OpenAPI client regenerated, CI green.

*Built (decision 2: a composer toggle):* the Answer / Guided radios became one segmented radio group (`components/ui/segmented.tsx`, 44px targets on phones) with **Try first** as the third option. Code: `backend/attempt_feedback.py`, `backend/api/routers/attempt.py`, `features/ask/{attempt.ts,attempt-feedback.tsx}`. A verdict that has no verified citation is shown as "unchecked"; notes that restate the hidden answer key (or contain code) are replaced by a neutral pointer. "Show me the evidence" asks for the cited answer into the same turn, and the passages the feedback cited stay reachable after it. Eval: `eval/attempts.jsonl`, `python -m eval.attempt_eval`.

### Phase 4: Understanding step
- **In your own words:** an editable note seeded from the answer's key distinction. Saved to the session notes (and `/history` when writes are allowed; browser storage in demo).
- **Similar example:** generate one new practice question on the same concept from the same passages, with the answer hidden behind a Try first flow (reuses Phase 3). Implement as an `/adaptive`-style call or a small `POST /practice/similar` endpoint (decide when building; prefer extending an existing route).
- **Save as flashcard:** front from the question or distinction, back from the user's note; `/cards` privately, browser-local cards in demo.
- "Ask for a different explanation" reuses `/adaptive` levels.

**Done when:** the full Question → Evidence → Understanding loop works end to end in both modes.

*Built (decision 3: a small `POST /practice/similar`, because its guards and response differ from `/adaptive`):* three closed rows under the answer, shown once a cited answer exists. The note is seeded from the answer without a model call and saved on the turn, in `/history` (`PUT /history/{id}/note`) where writes are allowed. A similar question is fetched only on click and answered through Try first against the passages it came from. `/adaptive` now accepts `context`. Code: `backend/similar_practice.py`, `features/ask/{understanding.ts,understanding-panel.tsx}`.

### Phase 5: Restyle the other pages
- **Library (Sources):** same rail and paper treatment; separate "Shared textbook (read-only)" from "Your documents (this browser)". Copy: "Material to learn. Lectern teaches it, with sources."
- **Practice:** flashcards review, LeetCode progress and study plan, Similar-example history. LeetCode "explain" gains a Try-first option using Phase 3.
- **Tools:** Tutor (concept map, synthesis, adaptive), Math, Visualize, Agent, Analytics restyled to the new tokens; no behaviour changes.

**Done when:** all 9 existing routes use the new shell and pass the visual suite at all widths and both themes.

*Built, with no new backend route or proxy entry:* the Library has a rail and a paper shelf (`.paper-tokens` re-points the desk tokens to paper inside a subtree). The public demo labels "Your documents (this browser)" and "Shared textbook (read-only)"; a private deployment has no browser documents, so it keeps "Add material" and "Indexed sources". Similar-example history reads the examples Ask already saved in this browser. LeetCode Try first judges an attempt against the problem statement plus up to three library passages, in one model call made on click.

### Phase 6: Verify, ship, update the portfolio
- Checks: `npm run web:typecheck && npm run web:lint && npm run web:test`, `.venv/bin/python -m pytest`, `ruff check .`, Playwright (default and `playwright.demo.config.ts`), production build.
- New screenshots in `docs/ui-refresh/after/`; update `docs/ui-refresh/README.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/API.md`.
- Deploy to the **existing** Vercel project (`apps/web`); do not create a new project or alias. Check the upload with a dry run first (`.vercelignore`).
- Live check with a handful of real requests only (Lambda concurrency quota is 10).
- Update the portfolio's Lectern case study images and copy to the shipped design.

### Phase 7 (optional, later): Study sets
Askretes groups work into classes. Without accounts, Lectern can offer **study sets**: a named group of documents plus saved questions and cards, stored locally (SQLite privately, browser storage in demo). Only build this if the earlier phases land well.

## 5. Non-goals
- Accounts, classes, professors, due dates or grading.
- Blocking answers. Guided and Try first are opt-in.
- Showing the prototype's illustrative answers or passages in the product.
- Renaming internal identifiers, storage keys or infrastructure (see `CLAUDE.md`).

## 6. Risks and constraints
- **Model calls per turn grow** (hints, feedback, similar example). Each counts against `DAILY_LLM_LIMIT` and adds load on a Lambda with a concurrency quota of 10. Mitigations: fetch hints lazily, cache per turn, never prefetch.
- **Feedback faithfulness:** a wrong "supported" verdict is worse than none. Require citations for verdicts and show uncited verdicts as unchecked.
- **Highlight accuracy:** the highlighted sentence is a heuristic; label it "closest match" and always show the full chunk on expand.
- **Demo boundaries:** new routes must stay read-only and keep visitor data in the browser.
- **Scope:** Phases 1–2 are the redesign the user asked for. Don't let 3–5 delay shipping them.

## 7. Open decisions
1. Default mode for new questions: Answer (recommended) or Guided.
2. Whether Try first appears as a composer toggle (recommended) or as its own entry point on the opening screen.
3. Similar example: extend `/adaptive` or add `/practice/similar`.
4. Whether to build Phase 7 study sets at all.
