# Data directory

| Path | Tracked in git? | What it is |
|---|---|---|
| `uploaded_files/sources.txt` | yes | URLs (YouTube, GitHub, web) to index, one per line |
| `uploaded_files/*.pdf`, audio | **no** | Your own study material. Drop files here locally. |
| `leetcode/normalized_problems.jsonl` | yes | Normalized LeetCode problem set (about 1.8k problems) |
| `leetcode/kaggle/` | yes | Raw Kaggle CSVs the normalized file was built from |
| `vector_store/` | no, generated | FAISS index, metadata and embeddings. Build with `python scripts/preprocess_all_documents.py` |
| `repos/` | no, generated | GitHub repos cloned by the GitHub source |

The textbook PDFs the project was developed with (*Data Structures Using Python*, *Dsa*, *Introduction to Computer Science*) are not redistributed. They stay in git history, but new clones of the working tree no longer include them. Use any CS PDFs you have the right to use.
