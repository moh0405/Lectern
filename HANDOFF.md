# Lectern handoff — start here

Last saved: **9 November 2026**. This file distinguishes the live product from the newer design exploration. The user's latest instruction is to save and commit context because their usage limit is running out. **Do not interpret this handoff as approval to implement or deploy the new prototype.**

## Current user direction

The user rejected the recently deployed Lectern layout. Their screenshot shows a narrow, centered application, small controls, a large form and substantial unused space. They want the project to look distinctive, use the available width properly, and see proposed designs before another implementation.

Three interactive design directions were created. The recommendation was **A: Evidence Desk**. The user then said, “okayy but you have to make it stand out.” A was refined as the working direction; the user has **not explicitly approved porting it to the production app**. Present the refined prototype and continue the design conversation when they return.

The original broader objective remains: improve Lectern UI/UX, deploy the approved product design, then update the portfolio's Lectern images/story to match. Do not confuse a successful deployment with design acceptance.

## Live product and repositories

| Item | Location |
| --- | --- |
| Live Lectern | https://lectern-tutor.vercel.app/ask |
| Canonical GitHub repo | https://github.com/moh0405/Lectern |
| Original local checkout | `/Users/momossss/Documents/GitHub/AI-study-mentor-` |
| Isolated UI worktree | `/Users/momossss/Documents/GitHub/.portfolio-refinement/lectern` |
| UI branch | `codex/lectern-product-ux` |
| Live portfolio | https://mohammadpetiwala.vercel.app/ |
| Portfolio Lectern case | https://mohammadpetiwala.vercel.app/work/lectern/ |
| Portfolio repo | https://github.com/moh0405/Portfoliowebsite |

Latest Lectern runtime commit at handoff: **`8ee7cd9`**. Latest portfolio runtime/content commit: **`5f9fd24`**. Later documentation commits preserve context and prototype files; inspect `git log` for their SHAs. Both original runtime checkouts were clean before this documentation work.

Vercel uses the existing project **`ai-study-mentor`**, project root `apps/web`, Node 22. The public alias remains `lectern-tutor.vercel.app`. The latest capacity-mitigation deployment was `ai-study-mentor-kegj2b114-mohammad-petiwalas-projects.vercel.app`; production was verified Ready. Do not create another Vercel project or replace the existing alias just to continue UI work.

## Most important artifact: committed design prototypes

**[Design options README](docs/ui-refresh/design-options/README.md)**

The complete prototype source, fonts, licenses, screenshots and browser checks are now under `docs/ui-refresh/design-options/`. This folder is documentation/design work; it is excluded from Vercel source upload and does not change production.

Start or resume the local preview:

```sh
cd docs/ui-refresh/design-options
python3 -m http.server 5435 --bind 127.0.0.1
```

- Compare: http://127.0.0.1:5435/
- Refined A: http://127.0.0.1:5435/?concept=a&state=answer
- A opening screen: http://127.0.0.1:5435/?concept=a
- B, Open Notebook: http://127.0.0.1:5435/?concept=b
- C, Study Studio: http://127.0.0.1:5435/?concept=c

The original scratch copy was `/Users/momossss/Documents/GitHub/lectern-design-options`. **Use the committed copy for future edits.** Its server now serves the canonical committed directory on the same port when this environment remains running.

### A: Evidence Desk — current design exploration

Full-width dark workspace with a library on the left, question/explanation in the middle, and a warm paper-like source margin on the right. The responsive phone layout stacks these areas rather than squeezing three columns.

Implemented prototype interactions:

1. **Question → Evidence → Understanding** navigation.
2. Clicking or keyboard-activating citation 01/02 changes the corresponding illustrative source and highlight.
3. A user-controlled source connector follows the selected citation on desktop; it is hidden on phones.
4. Source context expands/collapses.
5. Two small collision diagrams accept another illustrative key, showing chaining versus probing.
6. The Understanding view has an editable distinction, an in-session save, and a deterministic practice question.
7. Keyboard focus is restored after the prototype redraws.

**These are local, authored teaching examples.** No AI request is made, no uploaded document is processed, no real source provenance is invented, and the note is not saved to a production notebook. The final app must use actual retrieved citations; never show the illustrative collision answer for arbitrary user questions.

Screenshots to inspect first:

- [Refined evidence view](docs/ui-refresh/design-options/visuals/a-signature.png)
- [Understanding view](docs/ui-refresh/design-options/visuals/a-understanding.png)
- [Phone reflection](docs/ui-refresh/design-options/visuals/a-understanding-mobile.png)
- [All three directions](docs/ui-refresh/design-options/visuals/comparison.png)

### B and C

B, **Open Notebook**, is a warm reading-focused alternative with serif typography and source notes in the margin. C, **Study Studio**, pairs an explanation with a small practice panel and related source cards. They remain available for comparison; do not assume their controls are implemented product features.

## What was actually deployed before the design rejection

The Next.js application received:

- A shared full-height shell, grouped navigation, 44px controls, accessible mobile All tools disclosure and mobile command search.
- Persistent dark/light reading themes (`lectern-reading-theme` localStorage key).
- A larger Ask composer, optional Advanced controls, clearer question/answer and citation hierarchy, and clipboard-error guidance.
- A Sources redesign separating browser-local documents from the shared read-only textbook index; accurate file limits, loading/retry states and confirmed local deletion.
- A fix for long LeetCode study-plan titles causing horizontal overflow.
- Theme-aware Plotly legend/grid text that preserves the camera when changing theme.
- A loopback-only Next development origin configuration so headless previews at 127.0.0.1 hydrate properly.

Primary files: `apps/web/components/app-shell.tsx`, `app/globals.css`, `app/layout.tsx`, shared `components/ui/*`, `features/ask/*`, `features/sources/*`, `features/visualize/scatter3d.tsx`, and `features/leetcode/study-plan.tsx`.

The user dislikes the resulting visual direction. Preserve its working behavior while redesigning; do not simply roll back the fixes or describe the deployed design as accepted.

## Hosted failure found and mitigated

During live checking, requests returned bare HTTP429, including health. Read-only AWS checks confirmed an account Lambda concurrency quota of **10**, a peak of **10** concurrent executions for this function, and **12** throttles in the diagnostic window. Rapid browser navigation contributed to the burst. This was not proof of a permanently broken model or failed deployment. Later genuine hosted answer requests succeeded, including the captured binary-heap response.

Deployed in `8ee7cd9`:

- Successful public metadata GETs (`health`, `stats`, `documents`, `models`, `suggestions`) have a **10-second per-process cache and in-flight coalescing**.
- Bounded storage: 64 entries, 1MiB retained body data, 256KiB per entry; configuration/key/query/representation isolation and independent caller cancellation.
- Private/write-enabled configurations, searches, questions, writes and error responses bypass the cache. Shared metadata fetch deadline is 60 seconds to allow cold startup.
- Bare429 responses get useful busy guidance. Health distinguishes busy from offline. Answers and the embedding map offer explicit retry; answer retries are disabled while another question streams.

Important files: `apps/web/lib/backend-proxy.ts`, `backend-proxy.test.ts`, `lib/api.ts`, `lib/api.test.ts`, `components/app-shell.tsx`, `features/ask/turn-card.tsx`, `features/visualize/visualize-view.tsx`, `e2e/capacity.spec.ts`.

**The AWS capacity limit remains. No quota, reservation, spending limit, Python backend logic, retrieval benchmark, or model budget was increased/changed.** The cache is per process, not a distributed guarantee against load. Do not repeatedly sweep the production API to test layout. Use the temporary fixture for broad headless checks.

## Verification already completed

See [UI verification](docs/ui-refresh/README.md), the committed test sources, screenshots and provenance.

- Initial full production-mode browser integration: **58/58**.
- Independent Chrome/WebKit visual/interaction suite: **24/24**, all 9 routes, both themes, widths 1440/768/390/320.
- Real Plotly drag/theme/camera check: **4/4**.
- Public-demo browser workflow: **3/3**, including actual local PDF extraction/IndexedDB persistence, local-context answer and confirmed deletion.
- Opt-in real browser MiniLM/download-failure checks: **2/2**. Answers used FakeGemini; this was not a new answer-quality evaluation.
- Final frontend unit suite after capacity mitigation: **169 passed**.
- Final integration run: **61 tests completed** (60 first-pass, one Sources readiness-selector retry). The ambiguous selector matched the heading and a loading announcement; it was changed to the exact heading. Focused accessibility/capacity rerun: **13/13 clean**.
- Type checks, lint and production builds passed.
- Hosted binary-heap answer: HTTP200, model-labelled answer with citations, no browser exceptions; [capture record](docs/ui-refresh/live/verification.json).
- Hosted busy UI was checked with intercepted429 responses; final health check returned200.
- Design prototypes: **12 layout/basic checks**, then **10 refined-A interaction checks**, all passed, no browser exceptions or external requests.

A first hosted capture attempt timed out; subsequent actual requests completed. Do not turn these checks into an uptime, latency, semantic-quality or accessibility-conformance claim.

## Safe development / deployment continuation

1. Read `apps/web/AGENTS.md` and relevant docs under `node_modules/next/dist/docs/` before editing Next16.4 code.
2. Inspect Git status and current branches. Avoid overwriting user work or running multiple Next builds/dev servers against the same `.next` tree.
3. Continue design review from the committed prototype. Obtain the user's direction before applying another production redesign.
4. Port approved components into real Next components. Preserve SSE/cancel, citation verification, actual source text, browser-local storage, demo/private boundaries, keyboard access and reduced-motion behavior. Prototype routes/data are not app services.
5. Use the existing isolated fixture: `tests/e2e_server.py` creates temporary data and FakeGemini, not production/shared records.
6. Run relevant tests, then publish to the existing Vercel project only when implementation is authorized and ready.
7. Refresh the portfolio's actual hosted screenshots, text and caption provenance, validate it, and deploy that existing project as well.

Common checks from repo root:

```sh
npm ci
npm run web:test
npm run web:typecheck
npm run web:lint
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run web:build
CI=1 E2E_PYTHON=/absolute/path/to/a/python-with-project-dependencies npm exec -w apps/web -- playwright test -c playwright.config.ts
```

The last command starts the configured temporary API/frontend itself. It needs free8100/3100 and a compatible Python environment. Local Python used here: `/Users/momossss/Documents/GitHub/AI-study-mentor-/.venv/bin/python`. Demo tests use `playwright.demo.config.ts`, ports8300/3300. Real browser embedding tests require explicit `E2E_REAL_EMBEDDINGS=1`; broad real-model tests make provider calls and should not be run casually.

Existing project deployments use `vercel deploy --prod --yes --scope mohammad-petiwalas-projects` from the linked original checkout. **Do not run that for this documentation/prototype handoff.** `.vercelignore` excludes docs/private state/backend data while retaining `apps/web/app/api/backend`. Use a dry run to verify the upload if changing ignore rules; an unanchored `backend` pattern can accidentally remove the frontend proxy.

## Portfolio continuation

The portfolio has its own [agent handoff](https://github.com/moh0405/Portfoliowebsite/blob/main/AGENT_HANDOFF.md). Its current Lectern pictures match the deployed redesigned app, **not the unapproved Evidence Desk prototype**. Keep that distinction when updating imagery or assistant context.

Credentials stay in ignored local files and provider settings. No keys or cloud account/bucket/session identifiers belong in handoff files or public screenshots. Owner-only operations, shared-data writes and cloud-budget changes are separate from this design review.
