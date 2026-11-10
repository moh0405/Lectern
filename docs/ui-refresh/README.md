# Lectern product UX verification

This pass retains Lectern's retrieval, citation, storage and provider behavior while testing the redesigned learning workspace.

## Public baseline

`before/` contains actual read-only browser captures of https://lectern-tutor.vercel.app at 1440/390/320 widths. All API, model/provider download and non-GET requests were deliberately blocked. The offline/loading/error state in these images is therefore an audit condition, not evidence of a production API failure. See `before/README.md` and the recorded bounds/text JSON.

## Local execution boundary

The shared local preview uses `tests/e2e_server.py`: temporary storage, hashing embeddings and FakeGemini; no model key or cloud model call. Only the existing heaps.pdf and graphs.pdf test PDFs were indexed into the explicitly approved API 8420. After screenshots are actual rendered production UI with those 2 synthetic/test passages, not semantic embedding quality evidence or a live model result. The map correctly retains its hashing-embedder qualification. The health endpoint calls a populated vector index `semantic_search:true` even for this hashing fixture; that flag is not a separate semantic-quality validation.

The initial dev client stalled because Next16's development origin protection rejected127.0.0.1 resources/HMR. Root added the documented development allowed origin; subsequent browser checks observed successful health/stats/suggestion requests, enabled Ask on valid input, working theme state and keyboard navigation. No dependency downgrade was needed.

## Reproduce the focused UI checks

With an already-running loopback frontend connected only to the isolated scripted API:

```sh
LECTERN_UX_URL=http://127.0.0.1:3420 node node_modules/@playwright/test/cli.js test --config docs/ui-refresh/playwright.config.mjs
```

This config starts no server and performs no API data writes/model prompts. It runs Chrome and WebKit using the installed project's matching browser versions. The standard existing Playwright configuration also picks up `apps/web/e2e/ui-refresh.spec.ts` in its normal single-worker Chromium suite.

Coverage: all 9 learning destinations in dark/light modes at1440/768/390/320; actual heading bounds and horizontal page bounds; narrow focused-question hit testing; mobile All tools and Escape focus restoration; destination dismissal; theme persistence through navigation/reload and keyboard toggling; WCAG A/AA checks on every light-mode route. The existing integration tests retain ownership of actual upload/answer/citation/card/agent/math behavior on isolated temporary fixtures.

## Final result

The frozen production preview passed **24/24 Chrome and WebKit tests** in 1.1 minutes using the command above. All nine routes were checked in both themes at all four widths after actual loading skeletons resolved. The two earlier dev-only WebKit interruptions did not recur. Root separately reports the full regular production integration suite 58/58, unit suite 153, lint, types and build passing.

A real asynchronous-content overflow was found in the regular deployment's LeetCode study-plan grid (scrollWidth 557 at 390px and 553 at 320px). Root fixed its implicit auto-sized grid column/minimum item width. The geometry tests now wait for real query content and include the route in diagnostic messages; they do not accept the temporary skeleton as the final layout.

The light-mode Plotly legend was fixed and independently verified using actual rendered SVG text plus the plot layout: font #202939 matches theme foreground, legend background #fff matches the theme surface. An actual mouse drag changed the 3D camera; toggling theme preserved its eye, center and up coordinates. All 4 checks passed (`plot-theme-camera.json`).

`after/` contains 20 actual production screenshots with no development indicator. Ask-answer captures show an actual UI result from the isolated FakeGemini fixture/cache, clearly identified by the visible fake-model badge, with a citation to heaps.pdf. These establish interface behavior and provenance display, not real provider inference. No cloud model call, embedding download, real user upload, shared production data write or deployment was performed by this QA agent. Captures blocked every non-loopback request. Public before captures deliberately blocked APIs as documented; do not compare their backend/offline state as a service-quality benchmark.

Physical touch devices, real Safari on hardware, cloud latency and semantic embedding quality are outside this browser QA boundary. The default simulated map remains qualified as hashing-based. Final code/capture provenance is recorded in `capture-provenance.json`. All child-owned browsers are closed; servers remain owned by root.

## Owner integration checks

- Production build and type/lint checks passed with unchanged dependencies/backend contracts.
- 153 frontend unit tests passed.
- 58 production-mode end-to-end tests passed, including upload/indexing, streaming answers, citation inspection, agent steps, flashcards, exports, tutor tools, math, analytics, and all redesigned layouts.
- Three hosted-demo tests passed: browser flashcards, local practice progress, and PDF → IndexedDB → local-context answer → confirmed deletion. No document was uploaded to the shared server during the personal-documents check.
- Both opt-in real-browser embedding tests passed: the actual MiniLM model downloaded and found an answer through meaning search, and an intentionally blocked download kept keyword search functional with an explicit fallback notice. These checks used synthetic test PDFs and FakeGemini for the answer, not a paid hosted model or real user document.

Existing end-to-end expectations were updated to use the visible Advanced disclosure, the new confirmed deletion step, the user-facing passage terminology, and warning-specific status regions. Assertions continue to check the original behavior. The new library health status remains accessible without making unrelated warning assertions ambiguous.

The Python backend and generated API contracts are unchanged. These UI checks do not establish answer accuracy, a new retrieval benchmark, or clinical/production semantic quality. Deployment and portfolio capture follow this local verification.

## Follow-up: hosted capacity and recovery

A live browser sweep reproduced raw429responses, including health requests. Read-only AWS checks confirmed an account concurrency quota of10; the function reached10concurrent executions and CloudWatch recorded12throttles in the diagnostic window. A later hosted answer request succeeded (HTTP200, visible Gemini3.6response and source citations), so deployment failure and permanent provider unavailability were not established. No AWS quota, concurrency reservation, budget, or backend code was changed.

The frontend now distinguishes busy capacity from an offline API, explains bare429responses, and offers explicit retry actions for answers and the embedding map. Answer retries are disabled while another answer is streaming. The proxy coalesces successful shared metadata requests and caches them for10seconds per process, with64entry/1MiB retention bounds. Private/write-enabled deployments, search, questions, writes and error responses bypass this cache. Configuration and key rotation are isolated; one caller's cancellation cannot cancel other waiters. Shared metadata requests have a60second deadline to accommodate a cold backend.

169unit tests passed, including cache expiry/error/configuration/abort/bounds and busy/retry regressions. The61-test production integration run completed; an old partial-text Sources readiness selector matched both a heading and the new loading announcement, then passed on retry. That selector now targets the exact heading; the focused accessibility/capacity rerun passed all13tests without retries. No automatic live stress sweep will be repeated against the constrained backend.

Live captures in `live/` show the actual hosted workspace and a response from its shared textbook corpus. They are interface/provenance evidence, not a new retrieval or answer-quality benchmark. The final portfolio uses these hosted captures; independent staging screenshots remain labelled FakeGemini fixtures.
