# Phase 3: The TypeScript frontend

## Goal

Replace the Streamlit prototype with a real web application: Next.js and strict TypeScript, at parity with the old features, accessible, tested in a real browser.

## What was built (in shippable steps)

1. **Shell**: layout, theme, sidebar, status, command palette.
2. **Ask**: streaming answers with Stop, citation chips (verified/unverified), retrieved-passage cards with score and keyword highlights, mode picker, KaTeX math, notes export, flashcards CSV, history.
3. **Sources**: drag-and-drop upload, URL list, job progress, document table with delete.
4. **LeetCode**: filtered search, problem detail, AI study guide.
5. **Tutor**: concept map (React Flow + dagre), Socratic tutor, source synthesis, adaptive explanation.
6. **Math** and **Analytics** (charts, CSV report).
7. **Embedding map**: the real embeddings projected to 3D by the backend (PCA). The prototype's version plotted SHA-256 hashes, which are not embeddings at all.
8. **Parity check** then deletion of the Streamlit code (in its own commit, easy to revert).

## Technologies

Next.js 16 (App Router), React 19, TypeScript strict, Tailwind v4, TanStack Query, React Flow, Plotly, KaTeX, react-markdown, cmdk, Vitest, Playwright, axe-core. All explained in [the frontend stack](../concepts/09-frontend-stack.md).

## Decisions

- **Next.js over a Streamlit rewrite**: real routing, components, typed client, deployable on Vercel.
- **Reducer for streaming state** so the hardest logic is a pure, testable function.
- **Not ported: demo mode** (canned answers). Instead there is now a demo server (`scripts/demo_server.py`) with real retrieval and scripted answers, clearly labelled, used for the screenshots.
- **Error explained, not hidden**: when the model is unavailable the UI says why and still shows the retrieved passages.

## Bugs found

LeetCode topics were never parsed (0 of 1,825 had any); "two sum" ranked "Combine Two Tables" first; every data load re-hit Kaggle; the Ask history was wiped on mount (hydration); `apps/web/lib` was silently ignored by a Python `lib/` gitignore rule so a clean clone could not build; the accent colour and a scroll region failed WCAG.

## Result

A complete app with a11y checks on every page in CI. See the screenshots in the README.
