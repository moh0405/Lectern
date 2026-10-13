# 6. LLMs, prompting, streaming and citation checking

## The model

Generation uses Google's **Gemini** through the `google-genai` SDK (`backend/llm_config.py`, class `GeminiClient`). The model is a setting (`GEMINI_MODEL`), not a hard-coded name; `GET /api/v1/models` lists what your key can use, and the client resolves a configured name to an available one (cached) so a retired model name does not break the app.

An LLM predicts the next token (word piece) given everything before it. Everything it "knows" is either in its trained weights or in the prompt. RAG puts the facts in the prompt.

Key settings:

| Setting | Meaning | Here |
|---|---|---|
| `temperature` | randomness of sampling; 0 = most deterministic | default 0.2 for factual answers |
| `json_mode` | constrain output to valid JSON | used by concept map, Socratic questions and synthesis |
| streaming | receive tokens as they are produced | used for `/ask/stream` |

## Prompting for grounded answers

The prompt (see [RAG](01-rag.md)) does four things:

1. States a **role and mode** (technical, interview prep, quick summary).
2. Says to answer **only from the supplied context**.
3. Gives each passage a **label** `[document (page N)]` and asks the model to cite with the same label.
4. Gives permission to say **"not in the sources"**.

Other tools use the same machinery with different instructions: the **concept map** asks for JSON `{nodes, edges}`, the **Socratic tutor** for guiding questions and hints (never the answer), **synthesis** for similarities/conflicts across sources, **adaptive explanation** for a difficulty level, and the **LeetCode explainer** for a structured walkthrough.

## Streaming and Server-Sent Events (SSE)

Waiting for a full answer takes seconds; showing tokens as they arrive feels instant. `POST /api/v1/ask/stream` returns `text/event-stream`, a plain HTTP response that stays open and carries events:

```
event: meta
data: {"chunks": [...]}

event: token
data: {"text": "A hash table "}
event: token
data: {"text": "has to deal with "}
...
event: done
data: {"model": "...", "cached": false, "citations": [...], "unverified_citations": 0, "uncited": false}
```

On failure an `error` event carries `{code, message}` (`llm_unavailable`, `llm_error` or `retrieval_error`) and ends the stream. Why SSE rather than WebSockets: it is one-way (server to client), uses ordinary HTTP, works through proxies, and reconnects simply. The browser's built-in `EventSource` can only send GET, so the client in `packages/api-client/src/sse.ts` reads the `fetch` body stream and parses events itself.

## Hallucination and the citation checker

A model can cite a document that was never retrieved, or a real document at a page it never saw. Both look authoritative. `backend/citations.py` checks every citation in the finished answer against the passages that were actually in the prompt:

| Status | Meaning |
|---|---|
| `ok` | the document, and the page if given, were among the retrieved passages |
| `page_not_retrieved` | the document was retrieved but not that page |
| `unknown_source` | the document was not retrieved at all |

Plus **`uncited`**: a long answer (≥200 characters) from a request that had passages but cited none of them.

It is deliberately conservative about what counts as a citation: a bracket is a citation only if it has a page suffix (`(page 3)`, `, p. 3`), a file extension (`.pdf`), or exactly names a retrieved document. So `nums[0]` or `[1]` in code are never flagged. It accepts page ranges (`pages 12-13`) and sources without pages (`(page None)` is stripped; a false warning fixed after Phase 4).

What it does **not** prove: that the cited passage *supports* the claim. It catches fabricated or misplaced sources, which are the most embarrassing failures, but faithfulness scoring (an NLI model or LLM judge) is future work.

## Reliability features

- **Retries** with backoff on transient errors; clear typed errors (`llm_unavailable`) instead of exception text.
- **Empty / blocked responses** are errors, never cached.
- **Answer cache** (`backend/api/answer_cache.py`): key = (question, mode, k, model, temperature, store version). Repeat questions return instantly; changing the index invalidates entries.
- **No key?** Everything except generation still works.

## Fine-tuning vs retrieval (a decision this project made)

Fine-tuning changes a model's weights; RAG changes the model's input. For "answer from *my* documents, with citations, and stay current as documents change", RAG wins: no training cost, instant updates, auditable sources. Fine-tuning helps with style or domain behaviour, not with facts you want cited. And the measured failures here were retrieval failures. See [Phase 4](../phases/phase-4-retrieval-quality.md).

## Where to look

- `backend/llm_config.py`, `backend/rag_engine.py`, `backend/advanced_ai.py`
- `backend/api/routers/ask.py` (the SSE endpoint), `packages/api-client/src/sse.ts`
- `backend/citations.py`, `tests/test_citations.py`, `tests/fake_gemini.py` (the scripted model used in tests)
