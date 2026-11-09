"use client";

import { useQuery } from "@tanstack/react-query";
import { Library } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { api, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";
import { MyDocumentsCard } from "./my-documents-card";
import { DocumentsTable } from "./documents-table";
import { JobCard } from "./job-card";
import { UploadCard } from "./upload-card";
import { UrlCard } from "./url-card";
import styles from "./sources.module.css";

export function SourcesView() {
  const [jobs, setJobs] = useState<{ id: string; label: string }[]>([]);
  const addJob = (id: string, label: string) => setJobs((j) => [{ id, label }, ...j].slice(0, 5));
  const demo = useDemo();
  const stats = useQuery({ queryKey: ["stats"], queryFn: async () => unwrap(await api.http.GET("/api/v1/stats")) });

  return (
    <div className={`sources-library ${styles.library}`}>
      <PageHeader
        title="Sources"
        description="A library your answers can point back to. Add your material, then ask questions with the original passages in view."
      />
      {demo ? <MyDocumentsCard /> : (
        <section aria-label="Add source material" className="grid gap-4 lg:grid-cols-2">
          <UploadCard onJob={addJob} />
          <UrlCard onJob={addJob} />
        </section>
      )}
      {jobs.length ? (
        <section aria-label="Indexing jobs">
          <p className={`${styles.eyebrow} mb-3`}>Processing activity</p>
          <div className="grid gap-3 md:grid-cols-2">
            {jobs.map((j) => <JobCard key={j.id} jobId={j.id} label={j.label} />)}
          </div>
        </section>
      ) : null}
      <section aria-label={demo ? "Shared textbook collection" : "Source index overview"}>
        <div className={styles.statScope}>
          <span className="inline-flex items-center gap-2"><Library className="h-4 w-4" aria-hidden="true" />{demo ? "Shared textbook index" : "Server source index"}</span>
          <span>{demo ? "Separate from your browser-local documents" : "New or changed material is processed"}</span>
        </div>
        <dl className={styles.stats} aria-label={demo ? "Shared textbook statistics" : "Source index statistics"}>
          {[
            ["Documents", stats.data?.documents.toLocaleString()],
            ["Passages", stats.data?.chunks.toLocaleString()],
            ["Search mode", stats.data ? (stats.data.semantic_search ? "Semantic" : "Keyword") : undefined],
            ["Embedding model", stats.data?.embedder ?? (stats.data ? "Not configured" : undefined)],
          ].map(([label, value]) => (
            <div key={label} className={styles.stat}>
              <dt>{label}</dt><dd>{value ?? (stats.isError ? "Unavailable" : "…")}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4"><DocumentsTable /></div>
      </section>
    </div>
  );
}
