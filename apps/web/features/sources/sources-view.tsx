"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { api, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";
import { MyDocumentsCard } from "./my-documents-card";
import { DocumentsTable } from "./documents-table";
import { JobCard } from "./job-card";
import { UploadCard } from "./upload-card";
import { UrlCard } from "./url-card";

export function SourcesView() {
  const [jobs, setJobs] = useState<{ id: string; label: string }[]>([]);
  const addJob = (id: string, label: string) => setJobs((j) => [{ id, label }, ...j].slice(0, 5));
  const demo = useDemo();
  const stats = useQuery({ queryKey: ["stats"], queryFn: async () => unwrap(await api.http.GET("/api/v1/stats")) });

  return (
    <>
      <PageHeader
        title="Sources"
        description="Everything you add is split into passages and indexed, so answers can cite it. Only new or changed files are processed."
      />
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ["Documents", stats.data?.documents.toLocaleString()],
          ["Passages", stats.data?.chunks.toLocaleString()],
          ["Search", stats.data ? (stats.data.semantic_search ? "Semantic" : "Keyword") : undefined],
          ["Embedder", stats.data?.embedder ?? (stats.data ? "none yet" : undefined)],
        ].map(([label, value]) => (
          <Card key={label} className="p-4">
            <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
            <p className="mt-1 truncate text-lg font-semibold">{value ?? "…"}</p>
          </Card>
        ))}
      </div>

      {demo ? (
        <MyDocumentsCard />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <UploadCard onJob={addJob} />
          <UrlCard onJob={addJob} />
        </div>
      )}

      {jobs.length ? (
        <section aria-label="Indexing jobs" className="mt-4 grid gap-2 md:grid-cols-2">
          {jobs.map((j) => (
            <JobCard key={j.id} jobId={j.id} label={j.label} />
          ))}
        </section>
      ) : null}

      <div className="mt-4">
        <DocumentsTable />
      </div>
    </>
  );
}
