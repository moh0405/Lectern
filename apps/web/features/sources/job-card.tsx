"use client";

import { AlertTriangle, CheckCircle2, Trash2, XCircle } from "lucide-react";
import { useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { ApiError, errorMessage } from "@/lib/api";
import { plural } from "@/lib/format";
import { isFinished, useJob, type Job } from "./use-job";
import styles from "./sources.module.css";

interface Report {
  indexed?: string[];
  skipped?: string[];
  pruned?: string[];
  failed?: Record<string, string>;
  chunks_added?: number;
  chunks_removed?: number;
}

/** A backend progress line ("extracting x", "embedding 12 chunks from x") as a plain step for students. */
export function describeStep(job: Pick<Job, "status" | "progress">): string {
  if (job.status === "queued") return "Waiting to start…";
  const last = job.progress[job.progress.length - 1] ?? "";
  const embedding = /^embedding (\d+) chunks? from (.+)$/i.exec(last);
  if (embedding) return `Step 2 of 2: indexing ${plural(Number(embedding[1]), "passage")} from ${embedding[2]}…`;
  const extracting = /^extracting (.+)$/i.exec(last);
  if (extracting) return `Step 1 of 2: reading ${extracting[1]}…`;
  return last ? `${last.charAt(0).toUpperCase()}${last.slice(1)}` : "Starting…";
}

/** Why a source could not be added, in words a student can act on. The raw detail stays available. */
export function explainFailure(raw: string): string {
  const why = raw.toLowerCase();
  if (/not installed|install requirements|add it to requirements|no module named/.test(why))
    return "This server cannot read this kind of source yet: a component it needs is missing. Ask whoever runs this deployment to install it.";
  if (/cannot read file|no such file|permission denied/.test(why)) return "The file could not be opened. Check it is not damaged and upload it again.";
  if (/transcript|caption|subtitles/.test(why)) return "This video has no captions that could be read, so there is nothing to index.";
  if (/timed? ?out|timeout/.test(why)) return "The site took too long to respond. Try again later.";
  if (/\b(401|403)\b|forbidden|unauthori[sz]ed|access denied/.test(why)) return "The site refused access to this page. Try a publicly available link.";
  if (/\b404\b|not found/.test(why)) return "Nothing was found at this link. Check the address and try again.";
  if (/no text|empty|no content|scanned/.test(why)) return "No readable text was found. Scanned PDFs need selectable text (OCR) first.";
  return "This source could not be read, so nothing was added from it.";
}

function Failure({ name, raw }: { name?: string; raw: string }) {
  return (
    <ErrorNotice>
      <p>{name ? <span className="font-medium [overflow-wrap:anywhere]">{name}: </span> : null}{explainFailure(raw)}</p>
      <details className="mt-1 text-xs">
        <summary className="cursor-pointer underline underline-offset-2">Technical details</summary>
        <p className="mt-1 font-mono [overflow-wrap:anywhere]">{raw}</p>
      </details>
    </ErrorNotice>
  );
}

export function JobCard({ jobId, label, deleted = [], onGone }: {
  jobId: string;
  label: string;
  /** Sources deleted from the library since this job ran. */
  deleted?: string[];
  /** The server no longer knows this job (it restarted): stop showing it after a reload. */
  onGone?: (jobId: string) => void;
}) {
  const { data: job, error, refetch, isFetching } = useJob(jobId);
  const report = (job?.result ?? {}) as Report;
  const failed = Object.entries(report.failed ?? {});
  const running = job && !isFinished(job);
  const added = report.chunks_added ?? 0;
  const indexed = report.indexed ?? [];
  const notAdded = job?.status === "failed" || (job?.status === "done" && failed.length > 0 && indexed.length === 0 && added === 0);
  const removed = job?.status === "done" && indexed.length > 0 && indexed.every((key) => deleted.includes(key));
  const gone = error instanceof ApiError && error.status === 404;

  useEffect(() => {
    if (onGone && gone) onGone(jobId);
  }, [gone, jobId, onGone]);

  return (
    <Card className={`${styles.job} space-y-3 p-4`} data-testid="job-card">
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-sm font-medium" title={label}>{label}</span>
        {error ? <Badge className="border-bad/40 text-bad">Status unavailable</Badge> : !job ? (
          <Spinner />
        ) : removed ? (
          <Badge><Trash2 className="mr-1 h-3 w-3" aria-hidden="true" />Deleted</Badge>
        ) : notAdded ? (
          <Badge className="border-bad/40 text-bad"><XCircle className="mr-1 h-3 w-3" aria-hidden="true" />Not added</Badge>
        ) : job.status === "done" && failed.length ? (
          <Badge className="border-warn/40 text-warn"><AlertTriangle className="mr-1 h-3 w-3" aria-hidden="true" />Added with problems</Badge>
        ) : job.status === "done" ? (
          <Badge className="border-good/40 text-good"><CheckCircle2 className="mr-1 h-3 w-3" aria-hidden="true" />done</Badge>
        ) : (
          <Badge><Spinner className="mr-1 h-3 w-3" />{job.status === "queued" ? "Waiting" : "Processing"}</Badge>
        )}
      </div>

      {error ? <><ErrorNotice>{gone ? "The server no longer has a record of this job (it may have restarted). Check Indexed sources below to see whether it was added." : `${errorMessage(error)}. Status could not be checked; this does not confirm whether indexing finished.`}</ErrorNotice>{gone ? null : <Button size="sm" variant="secondary" disabled={isFetching} onClick={() => void refetch()}>{isFetching ? "Checking…" : "Retry status"}</Button>}</> : null}
      {job?.status === "failed" && job.error ? <Failure raw={job.error} /> : null}

      {running ? <p className={styles.jobProgress} role="status">{describeStep(job)}</p> : null}

      {removed ? (
        <p className="text-xs text-muted">Deleted from the library since it was added.</p>
      ) : job?.status === "done" && !notAdded ? (
        <p className="text-xs text-muted">
          {plural(added, "passage")} added
          {report.skipped?.length ? ` · ${report.skipped.length} unchanged` : ""}
          {report.chunks_removed ? ` · ${report.chunks_removed} replaced` : ""}
        </p>
      ) : null}
      {removed ? null : failed.map(([name, why]) => <Failure key={name} name={failed.length > 1 || name !== label ? name : undefined} raw={why} />)}
    </Card>
  );
}
