/**
 * LeetCode progress for the public demo. The server cannot keep it there (one shared database), so each
 * visitor's marks live in their own browser. The shape matches the API's `ProgressList` so the same
 * components render either source.
 */

export type LocalStatus = "todo" | "attempted" | "solved";

export interface LocalProgressItem {
  pid: string;
  title: string;
  status: LocalStatus;
  notes: string;
  attempts: number;
  difficulty: string;
  topics: string[];
  solved_at: number | null;
  updated_at: number;
}

export interface LocalProgressList {
  items: LocalProgressItem[];
  summary: { solved: number; attempted: number; todo: number; solved_by_difficulty: Record<string, number> };
}

export interface ProblemMeta {
  pid: string;
  title: string;
  difficulty: string;
  topics: string[];
}

const KEY = "ai-study-mentor:lc-progress:v1";
const STATUSES: LocalStatus[] = ["todo", "attempted", "solved"];

function isItem(v: unknown): v is LocalProgressItem {
  const i = v as LocalProgressItem;
  return !!i && typeof i.pid === "string" && STATUSES.includes(i.status) && typeof i.notes === "string" && Array.isArray(i.topics);
}

function read(): LocalProgressItem[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter(isItem) : [];
  } catch {
    return []; // storage blocked or corrupt: behave as empty
  }
}

function write(items: LocalProgressItem[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    // private window or full quota: the mark lasts until reload only
  }
}

export function summarize(items: LocalProgressItem[]): LocalProgressList {
  const solved_by_difficulty: Record<string, number> = {};
  let solved = 0;
  let attempted = 0;
  let todo = 0;
  for (const i of items) {
    if (i.status === "solved") {
      solved++;
      solved_by_difficulty[i.difficulty] = (solved_by_difficulty[i.difficulty] ?? 0) + 1;
    } else if (i.status === "attempted") attempted++;
    else todo++;
  }
  return { items, summary: { solved, attempted, todo, solved_by_difficulty } };
}

export function loadLocalProgress(): LocalProgressList {
  return summarize(read());
}

/** Set a status and/or notes. Omitted notes keep the old ones, as on the server. */
export function saveLocalProgress(problem: ProblemMeta, update: { status: LocalStatus; notes?: string }, now = Date.now() / 1000): LocalProgressItem {
  const items = read();
  const old = items.find((i) => i.pid === problem.pid);
  const next: LocalProgressItem = {
    ...problem,
    status: update.status,
    notes: update.notes ?? old?.notes ?? "",
    attempts: (old?.attempts ?? 0) + (update.status !== "todo" && update.status !== old?.status ? 1 : 0),
    solved_at: update.status === "solved" ? (old?.solved_at ?? now) : null,
    updated_at: now,
  };
  write([...items.filter((i) => i.pid !== problem.pid), next]);
  return next;
}
