import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { http: { GET: vi.fn(async () => ({ data: { documents: [{ source_key: "dsa.pdf", source_type: "pdf", docs: ["dsa.pdf"], chunks: 12 }] } })), DELETE: vi.fn() } },
  unwrap: (r: { data?: unknown }) => r.data,
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : "unknown"),
}));

import { DemoContext } from "@/lib/demo";
import { DocumentsTable } from "./documents-table";

const renderTable = (demo: boolean) =>
  render(
    <DemoContext.Provider value={demo}>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <DocumentsTable />
      </QueryClientProvider>
    </DemoContext.Provider>,
  );

describe("DocumentsTable", () => {
  it("offers deleting a source on a normal deployment", async () => {
    renderTable(false);
    expect(await screen.findByRole("button", { name: "Delete dsa.pdf" })).toBeInTheDocument();
  });

  it("does not offer deleting in the public demo, where the shared index is read-only", async () => {
    renderTable(true);
    expect(await screen.findByText("dsa.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Delete/ })).toBeNull();
  });
});
