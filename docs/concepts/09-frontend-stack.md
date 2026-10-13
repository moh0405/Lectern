# 9. The frontend stack

`apps/web/` is a TypeScript web app. This page explains each technology and why it was chosen.

## TypeScript (strict)

JavaScript plus types. The compiler (`tsc --noEmit`, run in CI) catches mistakes such as calling a function with the wrong shape or forgetting that a value can be `null`, before the code runs. `strict` mode turns on all the checks. The app was migrated from a Streamlit prototype to TypeScript in Phase 2.

## React 19

A library for building UIs from **components**: functions that take props and return markup. State changes re-render only what depends on them. Hooks (`useState`, `useEffect`, custom hooks like `useAskSession`) hold state and side effects.

## Next.js 16 (App Router)

A React framework that adds routing, building, and optimization.

- **File-based routing:** `app/ask/page.tsx` is the `/ask` page. Each page file here is a few lines that render a view from `features/`.
- `layout.tsx` wraps all pages (sidebar, providers); `error.tsx` / `global-error.tsx` / `not-found.tsx` handle failures.
- **Client components** (`"use client"`) are used for interactive views, since the data comes from the API in the browser.
- Next 16 changed some APIs relative to older tutorials; `apps/web/AGENTS.md` points to the bundled docs in `node_modules/next/dist/docs` instead of memory.

## Tailwind CSS v4

Utility classes in the markup (`flex gap-4 text-sm`) instead of separate stylesheets. Design tokens (colours, radii) are CSS variables in `app/globals.css`, with a dark theme. Small reusable primitives live in `components/ui/`, using `class-variance-authority` for variants and `tailwind-merge` to resolve class conflicts.

## TanStack Query

Manages **server state**: data owned by the backend (documents, stats, jobs, analytics). It caches results, de-duplicates requests, refetches when needed, retries (but not on 4xx errors), and supports polling (the Sources page polls a job until it finishes). You declare *what* you need (`useQuery({queryKey, queryFn})`) rather than hand-writing loading and error state in every component.

## The generated API client (`packages/api-client`)

`openapi-typescript` generates `schema.d.ts` from the backend's OpenAPI schema; `openapi-fetch` provides a typed client:

```ts
const { data, error } = await api.GET("/api/v1/documents");   // data and error are fully typed
```

Request bodies, query parameters and response shapes are checked at compile time. A small hand-written SSE reader (`src/sse.ts`) handles `/ask/stream`, which OpenAPI cannot describe as typed events.

## Streaming state machine (`features/ask`)

Streaming is easy to get subtly wrong (what if the user presses Stop? what if the network drops?). So the logic is a **pure reducer**:

```
events:  start → meta → token* → done | error | stop
state:   { phase, chunks, text, citations, error ... }
```

`session.ts` is the reducer (unit-tested without React); `use-ask-session.ts` connects it to the SSE stream. Only *finished* turns are saved to `localStorage`, so reloading mid-answer never leaves a half answer in history (a CI failure once caught a test that violated this).

## Rendering model output safely

Model text is **untrusted**. `react-markdown` renders it without raw HTML. Plugins: `remark-gfm` (tables), `remark-math` + `rehype-katex` (**KaTeX** typesets `$O(n \log n)$` formulas), `rehype-highlight` + `highlight.js` (code colouring), `remark-breaks`.

## Visualisation libraries

| Library | Used for |
|---|---|
| **React Flow** (`@xyflow/react`) + **dagre** | the concept map: dagre computes a tidy layered layout, React Flow draws nodes and edges |
| **Plotly** (`plotly.js-gl3d-dist-min`) | the 3D embedding map; loaded lazily, with a fallback message when WebGL is unavailable |
| plain SVG/CSS | the analytics charts |

## Other UI pieces

- `cmdk`: the Ctrl/Cmd+K **command palette** for jumping between pages.
- `lucide-react`: icons.
- `lib/use-url-params.ts`: keeps filters (LeetCode difficulty/topic, tutor tab) **in the URL**, so views are shareable and survive reload.

## Accessibility

Semantic landmarks, labelled controls, keyboard navigation, contrast checked in both themes, and an automated **axe-core** scan (WCAG A/AA) of every page in the browser tests.

## Layout of the code

```
app/          routes (tiny)
features/     ask, sources, leetcode, tutor, math, visualize, analytics (views, hooks, logic, tests)
components/   shell, palette, markdown, shared UI
lib/          API helpers, formatting, CSV/download, URL state
e2e/          Playwright specs
```

Run it: `npm install && npm run web:dev` from the repo root (the API must be running; see the README).
