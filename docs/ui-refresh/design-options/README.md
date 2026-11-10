# Lectern design options — canonical prototype source

These are **local design concepts**, not the deployed Lectern app. Start with [the full handoff](../../../HANDOFF.md).

## Latest state

The user rejected the deployed app's centered form, small scale and unused screen space. They asked to review stronger options first. Three directions were created:

| Direction | Visual/interaction identity |
| --- | --- |
| A — Evidence Desk | Full-width dark workspace, library, answer and warm source margin. Current recommendation and refined exploration. |
| B — Open Notebook | Warm paper, editorial reading typography and margin notes. |
| C — Study Studio | Visual explanations, sources and adjacent practice. |

The user's latest design comment was “okayy but you have to make it stand out.” A was refined in response. There is **no explicit approval yet to port A to the live app**.

## Run

No framework installation, backend, API key or cloud service is needed for preview:

```sh
cd docs/ui-refresh/design-options
python3 -m http.server 5435 --bind 127.0.0.1
```

Open http://127.0.0.1:5435/ to compare. Open `/?concept=a&state=answer` for refined A; `/?concept=a` for its opening state. Replace `a` with `b` or `c` for the other directions. The visible top controls switch opening/answer states.

## Files and behavior

- `index.html`: entry point.
- `style.css`: responsive layouts/typography and the citation/source treatment.
- `app.js`: templates and bounded local interactions; no model calls.
- `fonts/`: copied portfolio Manrope400/600 and Plex Mono400 assets, with upstream SIL Open Font License files.
- `visuals/`: desktop/phone captures and exact check results.
- `tests/layouts.mjs`: three-direction layout/basic checks.
- `tests/interactions.mjs`: refined Evidence Desk interactions.

Refined A supports citation-to-passage selection and highlight, optional source connector, context expansion, Question/Evidence/Understanding navigation, two deterministic collision diagrams, an editable in-session insight and a small practice question. Keyboard focus is restored after prototype redraws. The connector is suppressed on phones and respects reduced motion.

All passages, diagrams, notes and exercises are authored sample content. A submitted composer question gives a prototype notice; it does not fabricate an answer to arbitrary input. Hint-only controls state what the finished app would do. Notes survive only in this page session, not reloads. Real app implementation must connect to actual retrieval/citation/local-storage functionality.

## Verification

With the local preview running and the repo's matching Chromium installed:

```sh
node docs/ui-refresh/design-options/tests/layouts.mjs
node docs/ui-refresh/design-options/tests/interactions.mjs
```

Scripts resolve `playwright-core` from the repository dependencies, use loopback5435, and write screenshots/JSON back into `visuals/`. They make no provider/backend calls. Original reports:12layout/basic checks and10refined interaction checks passed with zero browser exceptions; the layout pass recorded zero external requests.

First images to inspect: `visuals/a-signature.png`, `visuals/a-understanding.png`, `visuals/a-understanding-mobile.png`, `visuals/comparison.png`.

## Deployment boundary

This directory sits under `/docs/`, excluded by the existing Vercel upload rules. It is committed for continuity, **not deployed or automatically imported into the product**. Do not replace the live UI or portfolio pictures with this illustrative prototype before the user chooses the direction and real implementation is complete.
