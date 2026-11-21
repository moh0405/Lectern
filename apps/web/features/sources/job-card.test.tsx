import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: { http: { GET: mocks.get } },
  unwrap: (response: { data?: unknown }) => response.data,
  errorMessage: (error: unknown) => error instanceof Error ? error.message : "unknown",
  ApiError: class ApiError extends Error { status = 500; },
}));
import { JobCard } from "./job-card";

const job = (over: object) => ({ data: { id: "j", kind: "index", status: "done", progress: [], result: null, error: null, created_at: 0, ...over } });
const renderCard = (deleted: string[] = []) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><JobCard jobId="j" label="https://example.com/a" deleted={deleted} /></QueryClientProvider>,
);
beforeEach(() => mocks.get.mockReset());

describe("JobCard", () => {
  it("shows a failed link as Not added, in student-facing words, with the raw detail tucked away", async () => {
    mocks.get.mockResolvedValue(job({ result: { indexed: [], failed: { "https://example.com/a": "beautifulsoup4 not installed. Add it to requirements." }, chunks_added: 0 } }));
    renderCard();
    expect(await screen.findByText("Not added")).toBeInTheDocument();
    expect(screen.queryByText(/done/)).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("cannot read this kind of source");
    expect(screen.getByText("Technical details")).toBeInTheDocument();
  });
  it("says when an added source has since been deleted", async () => {
    mocks.get.mockResolvedValue(job({ result: { indexed: ["heaps.pdf"], chunks_added: 3 } }));
    renderCard(["heaps.pdf"]);
    expect(await screen.findByText("Deleted")).toBeInTheDocument();
    expect(screen.queryByText(/passages added/)).toBeNull();
  });
  it("reports progress in passages", async () => {
    mocks.get.mockResolvedValue(job({ status: "running", progress: ["embedding 4 chunks from heaps.pdf"] }));
    renderCard();
    expect(await screen.findByRole("status")).toHaveTextContent("indexing 4 passages from heaps.pdf");
  });
});
