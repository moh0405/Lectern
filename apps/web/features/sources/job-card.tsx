"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { errorMessage } from "@/lib/api";
import { plural } from "@/lib/format";
import { isFinished, useJob } from "./use-job";
import styles from "./sources.module.css";

interface Report {
  indexed?: string[];
  skipped?: string[];
  pruned?: string[];
  failed?: Record<string, string>;
  chunks_added?: number;
  chunks_removed?: number;
}

export function JobCard({ jobId, label }: { jobId: string; label: string }) {
  const { data: job, error, refetch, isFetching } = useJob(jobId);
  const report = (job?.result ?? {}) as Report;
  const failed = Object.entries(report.failed ?? {});
  const running = job && !isFinished(job);

  return (
    <Card className={`${styles.job} space-y-3 p-4`} data-testid="job-card">
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-sm font-medium">{label}</span>
        {error ? <Badge className="border-bad/40 text-bad">Status unavailable</Badge> : !job ? (
          <Spinner />
        ) : job.status === "done" ? (
          <Badge className="border-good/40 text-good">
            <CheckCircle2 className="mr-1 h-3 w-3" />
            {failed.length ? "done with issues" : "done"}
          </Badge>
        ) : job.status === "failed" ? (
          <Badge className="border-bad/40 text-bad">
            <XCircle className="mr-1 h-3 w-3" />
            failed
          </Badge>
        ) : (
          <Badge>
            <Spinner className="mr-1 h-3 w-3" />
            {job.status}
          </Badge>
        )}
      </div>

      {error ? <><ErrorNotice>{errorMessage(error)}. Status could not be checked; this does not confirm whether indexing finished.</ErrorNotice><Button size="sm" variant="secondary" disabled={isFetching} onClick={() => void refetch()}>{isFetching ? "Checking…" : "Retry status"}</Button></> : null}
      {job?.error ? <ErrorNotice>{job.error}</ErrorNotice> : null}

      {running && job.progress.length ? <p className={styles.jobProgress} role="status">{job.progress[job.progress.length - 1]}</p> : null}

      {job?.status === "done" ? (
        <p className="text-xs text-muted">
          {plural(report.chunks_added ?? 0, "passage")} added
          {report.skipped?.length ? ` · ${report.skipped.length} unchanged` : ""}
          {report.chunks_removed ? ` · ${report.chunks_removed} replaced` : ""}
        </p>
      ) : null}
      {failed.map(([name, why]) => (
        <ErrorNotice key={name}>
          <span className="font-medium">{name}:</span> {why}
        </ErrorNotice>
      ))}
    </Card>
  );
}
