# Public UI baseline (2026-11-09)

Source: https://lectern-tutor.vercel.app. Headless Chromium, fresh browser storage; widths 1440/390/320. All screenshots are actual rendered public UI, not a mockup.

Safety and interpretation: all non-GET/HEAD requests, all `/api/*` requests and browser model/provider downloads were blocked. No question was submitted, no production data written, no external model called. Accordingly **API offline, unresolved/loading, empty, and error states here are intentional audit conditions and do not prove a production backend defect**. The general shots were captured 700ms after fonts settled. Files suffixed `settled-api-blocked` capture Sources/Embedding map after 6500ms retry settlement. See JSON for full observed text/bounds and blocked requests.

Concrete baseline observations:

1. Phone navigation is an unlabelled overflow strip. At 390px only 3 full tools and part of LeetCode fit; Agent starts x431, Embedding map x730, Analytics x890. Targets are 36px tall. The quick-jump control is hidden onmobile. All routes remain individually addressable; this is a discoverability/target-size problem, not missing functionality.
2. Ask shows a very broad settings/composer panel ondesktop; mobile puts 4 suggestion chips and 2 large selects before its submit action. Agentic implementation details compete with the primary learning task. A clearer question→evidence→answer hierarchy and progressive disclosure can reduce first-use effort.
3. Sources presents browser-local documents beside server-index counters and indexed sources. The distinction is explained in text, but visual hierarchy does not help the user choose a storage path confidently. Keep the privacy/storage semantics intact while making their separate roles explicit.
4. Nine equal sidebar destinations flatten common study actions and specialist tools. Grouping them with a clear current destination will improve orientation.

No horizontal document overflow was observed across the 27 route/viewport captures. Local scripted integration and actual source/answer/map states must be validated separately using `tests/e2e_server.py`, which isolates temp storage and replaces the model with FakeGemini.
