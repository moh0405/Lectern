# Presenting AI Study Mentor (about 3 minutes)

Run the API and the web app first (see the README), with some real study material indexed and a `GEMINI_API_KEY` set.

## Opening (20 s)
"AI Study Mentor is a tutor that answers from *your own* material and shows its evidence. It turns PDFs, lectures, repos and articles into a searchable index, then explains, quizzes and cites."

## Flow
1. **Sources** (30 s): drop a PDF and paste a YouTube link. Point out the live indexing job and that re-adding the same file is skipped (incremental).
2. **Ask** (60 s): ask a question about what you just added. Let the answer stream; open *Sources* to show the highlighted passages and relevance scores; click a YouTube citation to jump to the timestamp. Switch the style to *ELI5* and ask again.
3. **Tutor tools** (30 s): generate a *Concept map* for the topic, click a node. Try the *Socratic tutor* and reveal a hint.
4. **LeetCode** (30 s): filter Medium + Tree, open a problem, generate a study guide.
5. **Analytics** (10 s): the questions you just asked and which sources answered.

## Technical points to land
- RAG over mixed sources: chunking, embeddings (MiniLM), exact cosine search, grounded prompts with citations.
- FastAPI with streaming (Server-Sent Events) and background jobs; Next.js + TypeScript client generated from the OpenAPI schema.
- Quality: Python tests, Vitest, Playwright end to end, axe accessibility checks, CI on every push.

## If asked
- **Cost**: Gemini Flash; a question is a few thousand tokens.
- **Accuracy**: answers cite their sources, and the Ask page can show the exact prompt and the raw passages. Retrieval quality is measured in Phase 4 of the plan (`docs/PLAN.md`).
- **Privacy**: your files stay on the server you run; only retrieved passages and your question go to the model API.
- **No API key?** Retrieval, LeetCode search, math, the embedding map and analytics still work.
