import type { components } from "@ai-study-mentor/api-client";

export type AnalyticsSummary = components["schemas"]["AnalyticsSummary"];
export type AnalyticsEvent = components["schemas"]["AnalyticsEvent"];

/**
 * CSV cell, RFC 4180 quoting. Cells starting with = + - @ (or tab/CR) are prefixed with an apostrophe
 * so a spreadsheet will not run a question like "=HYPERLINK(...)" as a formula.
 */
export function csvCell(value: unknown): string {
  let s = value === null || value === undefined ? "" : String(value);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

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
