/**
 * Recent indexing jobs, kept in sessionStorage so leaving the page (or reloading it) does not
 * lose track of them: the Sources page resumes polling when you come back. Every access is guarded,
 * since storage can be blocked or full; then jobs simply last as long as the page does.
 */

export interface TrackedJob {
  id: string;
  label: string;
}

const KEY = "lectern-active-jobs";
const MAX = 5;

function isJob(v: unknown): v is TrackedJob {
  const j = v as TrackedJob;
  return !!j && typeof j.id === "string" && typeof j.label === "string";
}

export function loadActiveJobs(): TrackedJob[] {
  try {
    const raw: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter(isJob).slice(0, MAX) : [];
  } catch {
    return [];
  }
}

function save(jobs: TrackedJob[]): void {
  try {
    if (jobs.length) sessionStorage.setItem(KEY, JSON.stringify(jobs.slice(0, MAX)));
    else sessionStorage.removeItem(KEY);
  } catch {
    // blocked or full: jobs are tracked for this page view only
  }
}

export function rememberJob(job: TrackedJob): void {
  save([job, ...loadActiveJobs().filter((j) => j.id !== job.id)]);
}

/** The server no longer knows the job: stop resuming it. */
export function forgetJob(id: string): void {
  save(loadActiveJobs().filter((j) => j.id !== id));
}
