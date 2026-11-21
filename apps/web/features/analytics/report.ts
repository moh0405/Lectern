import type { components } from "@ai-study-mentor/api-client";
import { csvCell } from "@/lib/csv";

export { csvCell };

export type AnalyticsSummary = components["schemas"]["AnalyticsSummary"];
export type AnalyticsEvent = components["schemas"]["AnalyticsEvent"];

export function toCsv(events: AnalyticsEvent[]): string {
  const header = ["time", "question", "mode", "avg_score", "latency_ms", "tokens_prompt", "tokens_answer", "ok", "documents"];
  const rows = events.map((e) =>
    [new Date(e.ts * 1000).toISOString(), e.question, e.mode ?? "", e.avg_score.toFixed(3), e.latency_ms, e.tokens_prompt, e.tokens_answer, e.ok, e.docs.join("; ")]
      .map(csvCell)
      .join(","),
  );
  return [header.join(","), ...rows].join("\n") + "\n";
}

export function toReport(s: AnalyticsSummary): string {
  const docs = Object.entries(s.doc_usage);
  return [
    "# Study report",
    "",
    `- Questions asked: ${s.queries}`,
    `- Average relevance of retrieved passages: ${s.avg_score.toFixed(2)}`,
    `- Average response time: ${Math.round(s.avg_latency_ms)} ms`,
    `- Study streak: ${s.streak_days} ${s.streak_days === 1 ? "day" : "days"}`,
    "",
    "## Most used sources",
    "",
    ...(docs.length ? docs.map(([d, n]) => `- ${d}: ${n}`) : ["- none yet"]),
    "",
    "## Recent questions",
    "",
    ...(s.recent.length ? s.recent.map((e) => `- ${e.question.replace(/\s+/g, " ")}`) : ["- none yet"]),
    "",
  ].join("\n");
}

/** "just now", "5 min ago", "3 h ago", "yesterday", "4 days ago", then a short date. `ts` and `now` are in seconds. */
export function relativeTime(ts: number, now = Date.now() / 1000): string {
  const s = Math.max(0, Math.round(now - ts));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86_400) return `${Math.floor(s / 3600)} h ago`;
  const days = Math.floor(s / 86_400);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return new Date(ts * 1000).toLocaleDateString("en", { day: "numeric", month: "short", year: days > 300 ? "numeric" : undefined });
}

/** Fastest, slowest and latest of a series that runs oldest to newest. */
export function seriesRange(values: number[]): { min: number; max: number; latest: number } | null {
  const latest = values[values.length - 1];
  if (latest === undefined) return null;
  return { min: Math.min(...values), max: Math.max(...values), latest };
}

/** Points for a tiny inline sparkline: latencies oldest to newest scaled into a width x height box. */
export function sparkline(values: number[], width = 120, height = 28): string {
  if (values.length < 2) return "";
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  return values
    .map((v, i) => `${((i / (values.length - 1)) * width).toFixed(1)},${(height - ((v - min) / span) * (height - 2) - 1).toFixed(1)}`)
    .join(" ");
}
