# 11. Glossary

| Term | Meaning |
|---|---|
| **AUROC** | Area under the ROC curve. Chance that a random positive scores above a random negative. 1.0 perfect, 0.5 chance. |
| **Bootstrap (paired)** | Resample the test questions with replacement many times to estimate how uncertain a measured difference is. |
| **BM25** | Keyword ranking: rewards rare terms, saturates repeats, normalizes passage length. See [search](04-search-and-ranking.md). |
| **Chunk / passage** | A piece of a document (about 300-900 characters) that is embedded, stored and retrieved on its own. |
| **Citation check** | Verifying that `[doc (page N)]` in an answer refers to a passage that was in the prompt. |
| **Anki** | Flashcard software; imports CSV and `.apkg` files. |
| **Context window** | The maximum prompt size a model can read. |
| **Cosine similarity** | Cosine of the angle between two vectors; the standard similarity measure for embeddings. |
| **Cross-encoder** | A model that scores a (query, passage) pair together; accurate but slow; used for reranking. |
| **Dense retrieval** | Search by embedding similarity (vectors are "dense" lists of numbers). |
| **Dimension** | Length of a vector. MiniLM: 384. |
| **Embedding** | A vector representing the meaning of a text. See [embeddings](02-embeddings.md). |
| **Fine-tuning** | Further training a model's weights on your data. Not used here; see [LLMs](06-llms-and-prompting.md). |
| **Hallucination** | A fluent but unsupported or false model statement. |
| **Hit@k** | Share of questions with a relevant passage in the top k. |
| **Hybrid search** | Combining dense and keyword retrieval. |
| **IDF** | Inverse document frequency: how rare a term is across passages. |
| **Index (search)** | A data structure for fast lookup. BM25: an inverted index (term → passages). Vectors: the embedding matrix (or FAISS). |
| **JSON mode** | Asking the model to emit valid JSON; used for structured tutor tools. |
| **k (top-k)** | How many passages to retrieve. Default 3. |
| **L2 normalization** | Scaling a vector to length 1. Makes dot product equal cosine similarity. |
| **LLM** | Large language model (here Gemini). |
| **MRR** | Mean reciprocal rank: average of 1/rank of the first relevant result. |
| **NumPy** | Python library for fast array maths; powers vector search here. |
| **OpenAPI** | A standard, machine-readable description of an HTTP API. |
| **PCA** | Principal component analysis; projects high-dimensional vectors to few dimensions, used for the 3D map. |
| **Pydantic** | Python library for data validation via type-annotated classes. |
| **RAG** | Retrieval-augmented generation. See [RAG](01-rag.md). |
| **Rate limiting** | Capping how many requests a client can make per minute. |
| **Reranking** | Re-ordering a short candidate list with a slower, more accurate model. |
| **RRF** | Reciprocal rank fusion: merge ranked lists by summing 1/(k + rank). |
| **SSE** | Server-Sent Events: a one-way event stream over HTTP, used to stream answers. |
| **SM-2** | The spaced-repetition scheduling algorithm behind Anki's classic mode. See [study features](12-study-features.md). |
| **Stemming** | Reducing words to a base form (`collisions` → `collision`) so they match. |
| **Stopword** | A very common word ("the", "is") ignored by keyword search. |
| **Temperature** | Sampling randomness of a model; lower is more deterministic. |
| **Token** | A word piece; the unit models read and write. Not the same as a word. |
| **TanStack Query** | React library for fetching and caching server data. |
| **Vector** | An ordered list of numbers; here, an embedding. |
| **Vector database / store** | Storage that supports nearest-neighbour search over vectors. See [vector databases](03-vector-databases.md). |
| **WCAG** | Web Content Accessibility Guidelines; levels A, AA, AAA. |
