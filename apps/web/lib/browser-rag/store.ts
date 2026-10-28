/** Documents the visitor added, kept in this browser (IndexedDB). Nothing here is ever sent to the server except the few passages used for one question. */

import type { Passage } from "./chunk";

export interface StoredDoc {
  id: string;
  name: string;
  addedAt: number;
  pages: number;
  passages: Passage[];
  /** One unit vector per passage, laid end to end (`passages.length * dim` numbers), or null when meaning search was unavailable. */
  vectors: Float32Array | null;
  dim: number;
}

const DB = "ai-study-mentor-docs";
const STORE = "documents";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("Could not open browser storage"));
  });
}

async function run<T>(mode: IDBTransactionMode, work: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const req = work(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(req.result);
      tx.onerror = tx.onabort = () => reject(tx.error ?? new Error("Browser storage failed"));
    });
  } finally {
    db.close();
  }
}

export const listDocs = async (): Promise<StoredDoc[]> => ((await run("readonly", (s) => s.getAll())) as StoredDoc[]).sort((a, b) => b.addedAt - a.addedAt);
export const saveDoc = async (doc: StoredDoc): Promise<void> => void (await run("readwrite", (s) => s.put(doc)));
export const deleteDoc = async (id: string): Promise<void> => void (await run("readwrite", (s) => s.delete(id)));

export function newDocId(): string {
  return `doc-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/** The vector of passage `i` of a document. */
export const vectorAt = (doc: StoredDoc, i: number): Float32Array | null => (doc.vectors ? doc.vectors.subarray(i * doc.dim, (i + 1) * doc.dim) : null);
