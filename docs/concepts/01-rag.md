# 1. RAG: Retrieval-Augmented Generation

## The problem

A large language model (LLM) such as Gemini knows a lot, but:

1. It has never seen **your** material (your lecture notes, your textbook edition).
2. It can state wrong things with total confidence ("hallucination").
3. It cannot tell you *where* a claim came from.

You could paste your whole textbook into the prompt, but models have a limited context window, long prompts are slow and expensive, and models use information buried in the middle of a long prompt worse than information near the ends.

## The idea

**Don't give the model everything. Give it the few passages that matter, and make it answer from those.**

```
question ──► SEARCH your material ──► top 3 passages ──► PROMPT ──► LLM ──► answer + citations
                (retrieval)                              (augmented)  (generation)
```

That is the whole idea. "Retrieval-augmented generation" = retrieve first, then generate.

## The two halves

| Half | Question it answers | Quality measured by | In this repo |
|---|---|---|---|
| Retrieval | Did we find the right passages? | hit@k, MRR (see [evaluation](08-evaluation.md)) | `backend/vector_store.py`, `lexical.py`, `rag_engine.retrieve_context` |
| Generation | Did the model use them faithfully? | citation checks, human reading | `backend/llm_config.py`, `citations.py` |

If retrieval misses the right passage, **no model can answer correctly from it**. That is why most of the engineering effort here (Phases 3 and 4) went into retrieval, and why this project concluded fine-tuning a model would not help: the failures were retrieval failures (see [Phase 4](../phases/phase-4-retrieval-quality.md)).

## The pipeline here, step by step

**Offline (once per document):**

1. **Extract** text from the PDF / video / web page / repo / audio.
2. **Chunk**: cut it into passages of roughly 300 to 900 characters ([chunking](05-chunking.md)).
3. **Embed**: turn each passage into a vector ([embeddings](02-embeddings.md)).
4. **Store** passages, vectors and metadata ([vector databases](03-vector-databases.md)).

**Online (every question):**

5. **Embed the question** with the same model.
6. **Search** by meaning (vectors) and by words (BM25), then fuse the rankings ([search and ranking](04-search-and-ranking.md)).
7. **Build the prompt**: instructions + the top passages, each labelled like `[Data Structures.pdf (page 12)]` + the question.
8. **Generate** with Gemini, streamed token by token.
9. **Check citations**: every `[doc (page N)]` in the answer must refer to a passage that was in the prompt ([LLMs](06-llms-and-prompting.md)).

## What the prompt looks like

Conceptually (the real templates live in `backend/rag_engine.py`):

```
You are a study mentor. Answer ONLY from the context below.
Cite sources as [document (page N)]. If the answer is not in the context, say so.

Context:
- [hashing.md] Hash Tables > Collisions
  A collision occurs when two keys hash to the same bucket...
- [hashing.md] ...
- [graphs.md] ...

Question: How does a hash table handle collisions?
```

Two details matter:

- **Labels come from the retriever, not the model.** The model only copies them, which is what makes the citation check possible.
- **"Say so if the answer is not in the context"** gives the model a way out other than inventing something.

## Limits of RAG (honest)

- Retrieval can fail silently: a related but wrong passage still produces a fluent answer. This project shows each passage and its score next to the answer so you can judge.
- The model can still misread a correct passage. The citation check proves a citation *points at* a retrieved passage, not that the passage *supports* the claim. (Measuring that is future work.)
- Questions that need the whole document ("summarise chapter 3") are poorly served by top-3 passages; the synthesis tool in the Tutor page exists partly for that.

## Where to look in the code

| Step | File |
|---|---|
| orchestration | `backend/rag_engine.py` (`retrieve_context`, `generate_prompt`, `answer_with_gemini`) |
| HTTP | `backend/api/routers/ask.py` |
| prompt modes | `backend/rag_engine.py` (`_prompt_for_mode`: technical, interview prep, quick summary) |
| citation checking | `backend/citations.py` |
