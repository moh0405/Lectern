import { describe, expect, it } from "vitest";
import { csvCell, sparkline, toCsv, toReport, type AnalyticsEvent, type AnalyticsSummary } from "./report";

const event = (over: Partial<AnalyticsEvent> = {}): AnalyticsEvent => ({
  id: 1, ts: 1_700_000_000, question: "what is a heap", avg_score: 0.5, latency_ms: 120, tokens_prompt: 40,
  tokens_answer: 20, mode: "technical", docs: ["a.pdf", "b.pdf"], ok: true, ...over,
});

describe("csvCell", () => {
  it("quotes commas, quotes and newlines", () => {
    expect(csvCell('a,b')).toBe('"a,b"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell("line1\nline2")).toBe('"line1\nline2"');
    expect(csvCell("plain")).toBe("plain");
    expect(csvCell(null)).toBe("");
  });
  it("neutralises spreadsheet formulas", () => {
    for (const evil of ['=HYPERLINK("http://x")', "+1+1", "-2+3", "@SUM(A1)"]) {
      expect(csvCell(evil).replace(/^"/, "").startsWith("'")).toBe(true);
    }
  });
});

describe("toCsv / toReport", () => {
  it("writes a header and one row per event", () => {
    const lines = toCsv([event(), event({ question: "=cmd|' /C calc'!A0", ok: false })]).trim().split("\n");
    expect(lines).toHaveLength(3);
    expect(lines[0]).toBe("time,question,mode,avg_score,latency_ms,tokens_prompt,tokens_answer,ok,documents");
    expect(lines[1]).toContain("what is a heap,technical,0.500,120,40,20,true,a.pdf; b.pdf");
    expect(lines[2]).toContain("'=cmd");
  });
  it("renders a report even with no data", () => {
    const empty: AnalyticsSummary = { queries: 0, avg_score: 0, avg_latency_ms: 0, tokens_prompt: 0, tokens_answer: 0, doc_usage: {}, streak_days: 0, recent: [] };
    const md = toReport(empty);
    expect(md).toContain("Questions asked: 0");
    expect(md).toContain("- none yet");
  });
  it("singular streak", () => {
    expect(toReport({ ...({} as AnalyticsSummary), queries: 1, avg_score: 0.4, avg_latency_ms: 10, streak_days: 1, doc_usage: { "a.pdf": 2 }, recent: [event()] })).toContain("1 day\n");
  });
});

describe("sparkline", () => {
  it("needs two points", () => {
    expect(sparkline([5])).toBe("");
  });
  it("scales into the box", () => {
    const pts = sparkline([0, 10, 5], 100, 20).split(" ").map((p) => p.split(",").map(Number) as [number, number]);
    expect(pts[0]![0]).toBe(0);
    expect(pts[2]![0]).toBe(100);
    for (const [, y] of pts) {
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(20);
    }
    expect(pts[1]![1]).toBeLessThan(pts[0]![1]); // higher value, higher on screen (smaller y)
  });
});
