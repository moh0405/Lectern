# Lectern — RAG Learning Guide

This guide teaches you the full Retrieval-Augmented Generation (RAG) pipeline in small, incremental steps, with practical code references to this repository. It focuses on learning-by-doing while keeping the project stable and easy to commit frequently.

## What Is RAG?
RAG combines two ideas:
- Retrieval: find relevant context from your knowledge base for a user’s query.
- Augmented Generation: pass that context into an LLM to produce grounded answers.

Why RAG? It avoids full model retraining for every new domain and keeps answers tied to your documents.

## Components Overview
1. Data ingestion: load raw files (PDFs here) into text.
2. Chunking: split long text into manageable sections.
3. Embeddings: convert text chunks into numeric vectors capturing meaning.
4. Vector store: index embeddings and support similarity search (FAISS or NumPy).
5. Retrieval: select top-k relevant chunks for a query.
6. Prompting: build a careful, instruction-based prompt using retrieved context.
7. Generation: call an LLM (Gemini in this project) to answer.
8. Evaluation: verify correctness, citation, and faithfulness.

## Repository Map
- `backend/document_processor.py`: PDF reading, chunking, embeddings, and FAISS/metadata saving.
- `backend/rag_engine.py`: Loads vector store, retrieves top-k chunks, builds prompts. Now hardened with keyword fallback to avoid environment segfaults.
- `chat_cli.py --keyword`: Minimal CLI using keyword retrieval (no ML libs) to demonstrate end-to-end context selection and prompt creation. (The original `keyword_cli.py` was folded into it.)
- `chat_cli.py`: Semantic CLI that uses `RAGEngine` where embeddings are available. Falls back automatically.

## Step-by-Step Learning

### 1) Ingest and Chunk PDFs
- Read PDFs: extract raw text per page.
- Chunk text: split into ~500–1000 character chunks with overlap (~100–200) to keep context continuity.
- Why overlap? It preserves sentence continuity across chunk boundaries, improving retrieval quality.
Code: `read_pdf_text`, `chunk_text`, and `build_chunks_from_pdf` inside `backend/document_processor.py`.

### 2) Create Embeddings
- Use `sentence-transformers/all-MiniLM-L6-v2` (384 dims) to embed text chunks.
- Embeddings capture semantic meaning so similar texts are close in vector space.
- Potential macOS issues: Apple's Accelerate/MPS/Torch interactions can cause segfaults. This repo includes fallbacks.
Code: `embed_texts` inside `document_processor.py`. In `rag_engine.py`, embeddings are lazily generated and cached to `data/vector_store/embeddings.npy`.

### 3) Build the Vector Store
- Vector store: embeddings plus chunk metadata on disk (`embeddings.npy`, `chunks.jsonl`, `manifest.json`); search is exact cosine similarity, via NumPy or optionally FAISS. (The first prototype used FAISS plus a pickle file.)
- Metadata includes page content and source/page references for citation.
- If FAISS causes environment issues, the hardened `RAGEngine` can operate with precomputed embeddings or fall back to keyword retrieval.
Code: `build_faiss_index` and saving routines in `document_processor.py`. Loading and retrieval in `rag_engine.py`.

### 4) Retrieve Top-k Context
- Semantic search: compute query embedding, cosine similarity with chunk embeddings, pick top-k.
- Keyword fallback: share of query terms found in a chunk; useful when ML libs are unavailable.
Code: `retrieve_context` in `rag_engine.py` supports both paths.

### 5) Prompt Construction
- Structure prompt with strict instructions and a context block.
- Emphasize: use only provided context, be concise, cite sources.
Code: `generate_prompt` and `format_context` in `rag_engine.py`.

### 6) LLM Integration (Gemini)
- Once retrieval and prompts work, integrate an LLM. This project started with a local Ollama model and now uses Gemini through `GeminiClient`.
- Flow: `retrieve_context` → `generate_prompt` → LLM call → streamed answer.
- Keep generations deterministic where possible for reproducibility.
Code: `GeminiClient` in `backend/llm_config.py` and `RAGEngine.answer_with_gemini` in `rag_engine.py`.

## Training vs. RAG vs. Fine-tuning
- Training a foundation LLM from scratch is costly and complex.
- Fine-tuning adjusts an existing LLM’s weights on domain data; helps style but may “hallucinate” facts.
- RAG sidesteps weight changes; it augments the prompt with authoritative documents, improving grounding and freshness.

## Running the Current Demo
Option A (keyword-only retrieval, zero ML deps):
- `python3 chat_cli.py --keyword`
- Ask: "What is a linked list?"

Option B (semantic retrieval, if environment stable):
- Ensure requirements are installed.
- `python3 backend/rag_engine.py` or `python3 chat_cli.py`

## Environment Troubleshooting on macOS
- If you see segfaults during embedding or FAISS:
  - Use keyword-only CLI to continue learning (`chat_cli.py --keyword`).
  - Prefer CPU-only installs for Torch on macOS.
  - Try setting `OMP_NUM_THREADS=1` and avoiding MPS acceleration.
  - Keep `sentence-transformers` and `faiss-cpu` versions aligned; upgrade Torch if needed.

## Incremental Commits Strategy
- Keep each step small and validated:
  1. Add ingestion and chunking → run a chunk count.
  2. Save metadata and index files → confirm presence.
  3. Implement retrieval fallback → demo with `chat_cli.py --keyword`.
  4. Add semantic retrieval only after environment is stable.
  5. Integrate LLM last, after prompt looks good.

## Next Steps in This Project
1. Solidify CLI + retrieval flows (done for keyword; semantic on standby).
2. Add an LLM call wrapper (done: `GeminiClient`).
3. Build FastAPI endpoints: upload PDF, rebuild index, query.
4. Build a UI: upload/manage files, chat with retrieval (first Streamlit, now a Next.js app in `apps/web`).
5. Write evaluation harness: test questions, check citations.

Each of these will be implemented in small patches with a clear rationale and test instructions.