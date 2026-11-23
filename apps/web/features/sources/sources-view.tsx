"use client";

import { useQuery } from "@tanstack/react-query";
import { Library } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { api, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";
import { MyDocumentsCard } from "./my-documents-card";
import { DocumentsTable } from "./documents-table";
import { JobCard } from "./job-card";
import { forgetJob, loadActiveJobs, rememberJob, type TrackedJob } from "./job-store";
import { UploadCard } from "./upload-card";
import { UrlCard } from "./url-card";
import styles from "./sources.module.css";

export function SourcesView() {
  const [jobs, setJobs] = useState<TrackedJob[]>([]);
  const [deleted, setDeleted] = useState<string[]>([]);
  const addJob = (id: string, label: string) => {
    rememberJob({ id, label });
    setJobs((j) => [{ id, label }, ...j.filter((x) => x.id !== id)].slice(0, 5));
  };
  const settled = useCallback((id: string) => forgetJob(id), []);
  const demo = useDemo();
  const stats = useQuery({ queryKey: ["stats"], queryFn: async () => unwrap(await api.http.GET("/api/v1/stats")) });

  // Jobs started before a navigation or reload are picked up again (sessionStorage is browser-only, so after hydration).
  useEffect(() => {
    const saved = loadActiveJobs();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- restoring browser-only state once after hydration
    if (saved.length) setJobs((current) => [...current, ...saved.filter((s) => !current.some((c) => c.id === s.id))].slice(0, 5));
  }, []);

  return (
    <div className={`sources-library ${styles.library}`}>
      <PageHeader
        eyebrow="Library"
        title="Sources"
        description="Material to learn. Lectern teaches it, with sources."
      />
      <div className={styles.desk}>
      <nav className={styles.rail} aria-label="On this page">
        <p className="eyebrow">Your library</p>
        <a href="#library-yours">{demo ? "Your documents" : "Add material"}</a>
        <a href="#library-shared">{demo ? "Shared textbook" : "Indexed sources"}{stats.data ? <span>{stats.data.documents.toLocaleString()}</span> : null}</a>
      </nav>
      <div className={styles.shelves}>
      <div id="library-yours" className={styles.anchor}>
      {demo ? <MyDocumentsCard /> : (
        <section aria-label="Add source material" className="grid gap-4 lg:grid-cols-2">
          <UploadCard onJob={addJob} />
          <UrlCard onJob={addJob} />
        </section>
      )}
      </div>
      {jobs.length ? (
        <section aria-label="Indexing jobs">
          <p className={`${styles.eyebrow} mb-3`}>Processing activity</p>
          <div className="grid gap-3 md:grid-cols-2">
            {jobs.map((j) => <JobCard key={j.id} jobId={j.id} label={j.label} deleted={deleted} onGone={settled} />)}
          </div>
        </section>
      ) : null}
      <section id="library-shared" className={`paper paper-tokens ${styles.shelf} ${styles.anchor}`} aria-label={demo ? "Shared textbook collection" : "Source index overview"}>
        <div className={styles.statScope}>
          <span className="inline-flex items-center gap-2"><Library className="h-4 w-4" aria-hidden="true" />{demo ? "Shared textbook index" : "Server source index"}</span>
          <span>{demo ? "Separate from your browser-local documents" : "New or changed material is processed"}</span>
        </div>
        <dl className={styles.stats} aria-label={demo ? "Shared textbook statistics" : "Source index statistics"}>
          {[
            ["Documents", stats.data?.documents.toLocaleString()],
            ["Passages", stats.data?.chunks.toLocaleString()],
            [demo ? "Textbook search mode" : "Search mode", stats.data ? (stats.data.semantic_search ? "Semantic" : "Keyword") : undefined],
            ["Embedding model", stats.data?.embedder ?? (stats.data ? "Not configured" : undefined)],
          ].map(([label, value]) => (
            <div key={label} className={styles.stat}>
              <dt>{label}</dt><dd>{value ?? (stats.isError ? "Unavailable" : "…")}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4"><DocumentsTable onDeleted={(key) => setDeleted((d) => [...d, key])} /></div>
      </section>
      </div>
      </div>
    </div>
  );
}
