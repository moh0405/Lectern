"use client";

import { ArrowUpRight, Database, FileText, HardDrive, Info, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState, useSyncExternalStore, type DragEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge, ErrorNotice, Notice, Spinner } from "@/components/ui/feedback";
import { chunkPages } from "@/lib/browser-rag/chunk";
import { EMBEDDING_DIM, embedTexts, embeddingsEnabled, loadEmbedder } from "@/lib/browser-rag/embed";
import { ACCEPT, MAX_FILE_MB, extractPages } from "@/lib/browser-rag/extract";
import { deleteDoc, newDocId, saveDoc } from "@/lib/browser-rag/store";
import { LOCAL_DOCS_KEY, useLocalDocs } from "@/lib/browser-rag/use-local-docs";
import { errorMessage } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import styles from "./sources.module.css";

const MAX_PASSAGES = 8000;
const subscribeToBrowser = () => () => {};

/** Public-demo documents stay in IndexedDB; only matching passages are sent when asking. */
export function MyDocumentsCard() {
  const qc = useQueryClient();
  const docs = useLocalDocs();
  const input = useRef<HTMLInputElement>(null);
  const processing = useRef(false);
  const controlId = useId();
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [keywordOnly, setKeywordOnly] = useState(false);
  const [limited, setLimited] = useState<string[]>([]);
  const [completion, setCompletion] = useState("");
  const [confirm, setConfirm] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);
  // Hydration must finish before a file picker can safely handle a selection.
  const ready = useSyncExternalStore(subscribeToBrowser, () => true, () => false);
  const storageSupported = !ready || typeof indexedDB !== "undefined";

  useEffect(() => { if (confirm) document.getElementById(`${controlId}-confirm`)?.focus(); }, [confirm, controlId]);

  function cancelRemove(id: string) {
    setConfirm(null);
    setRemoveError(null);
    requestAnimationFrame(() => document.getElementById(`${controlId}-${encodeURIComponent(id)}`)?.focus());
  }

  async function addFile(file: File) {
    setBusy(`Reading ${file.name}…`);
    const pages = await extractPages(file, (n, total) => setBusy(`Reading ${file.name}: page ${n} of ${total}`));
    const allPassages = chunkPages(pages);
    const passages = allPassages.slice(0, MAX_PASSAGES);
    setBusy(`Preparing ${file.name} for meaning search…`);
    await loadEmbedder((s) => setBusy(s));
    const vectors = await embedTexts(
      passages.map((p) => p.text),
      (done, total) => setBusy(`Indexing ${file.name}: ${done} of ${total} passages`),
    );
    const flat = vectors ? new Float32Array(vectors.length * EMBEDDING_DIM) : null;
    vectors?.forEach((v, i) => flat!.set(v, i * EMBEDDING_DIM));
    await saveDoc({ id: newDocId(), name: file.name, addedAt: Date.now(), pages: pages.length, passages, vectors: flat, dim: EMBEDDING_DIM });
    if (!vectors && embeddingsEnabled()) setKeywordOnly(true);
    if (allPassages.length > MAX_PASSAGES) setLimited((current) => [...current, file.name]);
    await qc.invalidateQueries({ queryKey: LOCAL_DOCS_KEY });
  }

  async function addFiles(list: FileList | File[] | null) {
    const files = Array.from(list ?? []);
    if (!files.length || processing.current || !ready || !storageSupported) return;
    processing.current = true;
    setErrors([]);
    setKeywordOnly(false);
    setLimited([]);
    setCompletion("");
    let added = 0;
    try {
      for (const file of files) {
        try { await addFile(file); added += 1; }
        catch (error) { setErrors((prev) => [...prev, `${file.name}: ${errorMessage(error)}`]); }
      }
      if (added) setCompletion(`${plural(added, "document")} added to this browser. Ready to ask about.`);
    } finally {
      setBusy(null);
      processing.current = false;
    }
  }

  async function removeDocument(id: string) {
    setRemoving(id);
    setRemoveError(null);
    try {
      await deleteDoc(id);
      await qc.invalidateQueries({ queryKey: LOCAL_DOCS_KEY });
      setConfirm(null);
      setCompletion("Document removed from this browser.");
    } catch (error) {
      setRemoveError(errorMessage(error));
    } finally { setRemoving(null); }
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    void addFiles(event.dataTransfer.files);
  };

  return (
    <Card aria-label="My documents" className={`sources-local-card ${styles.localCard}`}>
      <div className={styles.sectionHead}>
        <div>
          <div className={styles.titleRow}><CardTitle>My documents</CardTitle><span className={styles.scope}><HardDrive className="h-3 w-3" aria-hidden="true" />This browser only</span></div>
          <p className="text-muted">Your course notes, readings, and PDFs. Files are read and searched here; only matching passages are sent to the model when you ask a question.</p>
        </div>
      </div>
      <div
        onDragOver={(event) => { event.preventDefault(); if (!processing.current && storageSupported) setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={cn(styles.dropzone, over && styles.dropOver)}
      >
        <span className={styles.dropIcon}>{busy ? <Spinner className="h-5 w-5" /> : <Upload className="h-5 w-5" aria-hidden="true" />}</span>
        <div className={styles.dropCopy}>
          <p role="status" aria-live="polite">{busy ?? "Drop your study material here"}</p>
          <span>PDF, plain text, or Markdown · up to {MAX_FILE_MB} MB per file</span>
        </div>
        <Button type="button" onClick={() => input.current?.click()} disabled={busy !== null || !ready || !storageSupported}>Choose files</Button>
        {ready ? <input ref={input} type="file" multiple accept={ACCEPT} aria-label="Add my documents" className="sr-only" disabled={busy !== null || !storageSupported} onChange={(event) => { void addFiles(event.target.files); event.target.value = ""; }} /> : null}
      </div>
      <div className={styles.details}><Info aria-hidden="true" /><p>{embeddingsEnabled() ? "Meaning search downloads a model on first use (about 25 MB, then cached). Large books can take a few minutes." : "Meaning search is disabled on this deployment; documents use keyword search."} Scanned PDFs need selectable text or OCR first.</p></div>
      <div className={styles.details}><Database aria-hidden="true" /><p>Documents stay in this browser’s storage, not the shared textbook index. Clearing browser data removes them; keep your original files. Storage capacity depends on your device.</p></div>
      {!storageSupported ? <ErrorNotice className="mt-3">This browser does not support the document storage Lectern needs. Try a browser with IndexedDB enabled. Shared textbooks below are still available.</ErrorNotice> : null}
      {keywordOnly ? <Notice className="mt-3">Meaning search was unavailable for one or more added documents, so they use keyword search only. Adding them again later may enable meaning search.</Notice> : null}
      {limited.map((name, index) => <Notice key={`${name}-${index}`} className="mt-3">{name}: only the first {MAX_PASSAGES.toLocaleString()} passages were indexed. Split a large document to search the remaining material.</Notice>)}
      {errors.map((message, index) => <ErrorNotice key={`${index}-${message}`} className="mt-3"><p>{message}</p><p className="mt-1">Check the file and browser storage permissions, then choose it again to retry.</p></ErrorNotice>)}
      {completion && !busy ? <p className="mt-3 text-sm text-good" role="status">{completion}</p> : null}
      {docs.isPending ? <p className="mt-4 text-sm text-muted" role="status">Loading documents from this browser…</p> : docs.data?.length ? (
        <ul className={styles.localList} aria-label="Your documents">
          {docs.data.map((document) => (
            <li key={document.id} className={`${styles.row} ${styles.localRow}`}>
              <span className={styles.rowIcon}><FileText className="h-4 w-4" aria-hidden="true" /></span>
              <div className={styles.rowBody}>
                <p className={styles.rowName}>{document.name}</p>
                <div className={styles.rowMeta}><span>{plural(document.pages, "page")} · {plural(document.passages.length, "passage")}</span><Badge>{document.vectors ? "meaning + keyword search" : "keyword search"}</Badge></div>
              </div>
              <div className={styles.rowActions}>
                {confirm === document.id ? <div className={styles.confirm} role="group" aria-label={`Remove ${document.name}?`} onKeyDown={(event) => { if (event.key === "Escape" && removing === null) cancelRemove(document.id); }}>
                  <p>Remove this document and its search index from this browser? Keep the original file to add it again.</p>
                  <div className={styles.confirmActions}>
                    <Button id={`${controlId}-confirm`} variant="danger" size="sm" disabled={removing !== null} onClick={() => void removeDocument(document.id)}>{removing === document.id ? "Removing…" : "Confirm remove"}</Button>
                    <Button variant="ghost" size="sm" disabled={removing !== null} onClick={() => cancelRemove(document.id)}>Cancel</Button>
                  </div>
                </div> : <Button id={`${controlId}-${encodeURIComponent(document.id)}`} variant="ghost" size="icon" aria-label={`Remove ${document.name}`} onClick={() => { setConfirm(document.id); setRemoveError(null); }}><Trash2 className="h-4 w-4" aria-hidden="true" /></Button>}
              </div>
            </li>
          ))}
        </ul>
      ) : <p className={styles.emptyLocal}><FileText className="h-4 w-4 shrink-0" aria-hidden="true" />No documents added in this browser yet. Choose a file above to begin.</p>}
      {removeError ? <ErrorNotice className="mt-3">Could not remove this document: {removeError}. Try again; the document has not been marked as removed.</ErrorNotice> : null}
      {docs.data?.length ? <div className={styles.footerAction}><p>{plural(docs.data.length, "document")} in this browser</p><Link href="/ask">Ask about your documents <ArrowUpRight className="h-4 w-4" aria-hidden="true" /></Link></div> : null}
    </Card>
  );
}
