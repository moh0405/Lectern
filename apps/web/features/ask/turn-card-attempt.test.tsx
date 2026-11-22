import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as rtlRender, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ api: { http: { POST: vi.fn() } }, unwrap: (r: { data?: unknown }) => r.data, errorMessage: () => "x" }));

import { TurnCard } from "./turn-card";
import type { AttemptFeedback, Turn } from "./session";

const client = new QueryClient();
const render = (ui: React.ReactElement) => rtlRender(ui, { wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });

const chunks = [
  { text: "Insert sifts the key up.", doc: "heaps.pdf", page: 2, score: 0.8 },
  { text: "Height is log n.", doc: "trees.pdf", page: 5, score: 0.6 },
];
const ok = (doc: string, page: number) => ({ label: `${doc} (page ${page})`, doc, page, status: "ok" as const });
const feedback: AttemptFeedback = {
  format: "steps",
  units: ["Put it at the bottom.", "Swap it down.", "I think the height is log n.", "Heaps are blue."],
  items: [
    { unit: 1, ref: "Step 1", verdict: "supported", note: "Matches the passage.", citations: [ok("heaps.pdf", 2)], checked: true },
    { unit: 2, ref: "Step 2", verdict: "contradicted", note: "Which way does it move?", citations: [ok("heaps.pdf", 2), ok("trees.pdf", 5)], checked: true },
    { unit: 3, ref: "Step 3", verdict: "supported", note: "Say which passage.", citations: [{ label: "Made up.pdf (page 1)", doc: "Made up.pdf", page: 1, status: "unknown_source" }], checked: false },
    { unit: 4, ref: "Step 4", verdict: "not_covered", note: "Not in your notes.", citations: [], checked: false },
  ],
  summary: "Look at step 2 first.",
  chunks,
  unverified_citations: 1,
  withheld: 0,
};
const params = { question: "why log n", k: 3, temperature: 0.2 };
const turn = (over: Partial<Turn> = {}): Turn => ({
  id: "t", question: "Why is heap insert O(log n)?", answer: "", chunks, status: "done",
  attempt: { params, text: feedback.units.join("\n"), format: "steps", feedback, evidenceStarted: false }, ...over,
});

describe("TurnCard with Try first feedback", () => {
  it("marks every step with its verdict and opens the cited passage with the step as the highlight", async () => {
    const onSelect = vi.fn();
    const onEvidence = vi.fn();
    render(<TurnCard turn={turn()} onStop={() => {}} onRemove={() => {}} onSelect={onSelect} onEvidence={onEvidence} selection={{ ref: null, chunk: null }} />);
    const section = screen.getByRole("region", { name: "Feedback on your steps" });
    expect(section).toHaveTextContent("Look at step 2 first.");
    expect(section).toHaveTextContent("1 supported · 1 to re-check · 1 not checked against your sources · 1 not in your sources");
    const rows = within(screen.getByRole("list", { name: "Your attempt, step by step" })).getAllByRole("listitem");
    expect(rows.map((r) => r.getAttribute("data-verdict"))).toEqual(["supported", "contradicted", "unchecked", "not_covered"]);

    await userEvent.click(screen.getByRole("button", { name: "Step 2: Contradicted by your sources. Open passage 1 in the source margin" }));
    expect(onSelect).toHaveBeenLastCalledWith({ ref: null, chunk: 0, sentence: "Swap it down." });
    await userEvent.click(within(rows[1]!).getByRole("button", { name: "Open passage 2 in the source margin" }));
    expect(onSelect).toHaveBeenLastCalledWith({ ref: null, chunk: 1, sentence: "Swap it down." });

    // An uncited or unverified verdict is never a confident marker, and it says why.
    expect(within(rows[2]!).queryByRole("button")).toBeNull();
    expect(rows[2]).toHaveTextContent("Looks right, unchecked");
    expect(rows[2]).toHaveTextContent("not checked against your sources");
    expect(rows[2]).toHaveTextContent("Cites [Made up.pdf (page 1)], but that source was not among the passages it was given.");
    expect(within(rows[3]!).queryByRole("button")).toBeNull();
    expect(rows[3]).toHaveTextContent("Not in your sources");

    // No answer yet: no copy or flashcard actions, and the answer is only fetched on request.
    expect(screen.queryByRole("button", { name: "Copy answer" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Show me the evidence" }));
    expect(onEvidence).toHaveBeenCalledTimes(1);
  });

  it("shows progress while checking, and drops the evidence button once the answer is asked for", () => {
    const { rerender } = render(<TurnCard turn={turn({ status: "streaming", chunks: [], attempt: { params, text: "x", format: "code", language: "Python", evidenceStarted: false } })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByText("Checking your attempt against your sources…")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Feedback on your code/ })).toHaveTextContent("Python");
    expect(screen.queryByText("Building your answer")).toBeNull();
    rerender(<QueryClientProvider client={client}><TurnCard turn={turn({ answer: "Sift up [heaps.pdf (page 2)].", attempt: { params, text: "x", format: "steps", feedback, evidenceStarted: true } })} onStop={() => {}} onRemove={() => {}} /></QueryClientProvider>);
    expect(screen.queryByRole("button", { name: "Show me the evidence" })).toBeNull();
    expect(screen.getByRole("region", { name: "Feedback on your steps" })).toBeInTheDocument();
    expect(screen.getByText("Sift up", { exact: false })).toBeInTheDocument();
  });

  it("names a stopped feedback request as such", () => {
    render(<TurnCard turn={turn({ status: "stopped", attempt: { params, text: "x", format: "steps", evidenceStarted: false } })} onStop={() => {}} onRemove={() => {}} onFresh={() => {}} />);
    expect(screen.getByText(/You stopped this feedback request/)).toBeInTheDocument();
  });
});
