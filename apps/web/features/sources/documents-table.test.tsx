import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ get: vi.fn(), remove: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: { http: { GET: mocks.get, DELETE: mocks.remove } },
  unwrap: (response: { data?: unknown }) => response.data,
  errorMessage: (error: unknown) => error instanceof Error ? error.message : "unknown",
}));
import { DemoContext } from "@/lib/demo";
import { DocumentsTable } from "./documents-table";

const document = { source_key: "dsa.pdf", source_type: "pdf", docs: ["dsa.pdf"], chunks: 12 };
const renderTable = (demo: boolean) => render(
  <DemoContext.Provider value={demo}><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><DocumentsTable /></QueryClientProvider></DemoContext.Provider>,
);
beforeEach(() => { mocks.get.mockReset().mockResolvedValue({ data: { documents: [document] } }); mocks.remove.mockReset().mockResolvedValue({ data: {} }); });

describe("DocumentsTable", () => {
  it("offers deleting a source on a normal deployment", async () => {
    renderTable(false);
    expect(await screen.findByRole("button", { name: "Delete dsa.pdf" })).toBeInTheDocument();
  });
  it("does not offer deleting in the read-only public collection", async () => {
    renderTable(true);
    expect(await screen.findByText("dsa.pdf")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Shared textbooks" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Delete/ })).toBeNull();
  });
  it("requires confirmation and supports cancel without deleting", async () => {
    renderTable(false);
    fireEvent.click(await screen.findByRole("button", { name: "Delete dsa.pdf" }));
    expect(mocks.remove).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Confirm delete" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("button", { name: "Confirm delete" })).toBeNull();
    expect(mocks.remove).not.toHaveBeenCalled();
  });
  it("retains a failed deletion for an explicit retry", async () => {
    mocks.remove.mockRejectedValueOnce(new Error("Connection unavailable"));
    renderTable(false);
    fireEvent.click(await screen.findByRole("button", { name: "Delete dsa.pdf" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not been marked as deleted");
    expect(screen.getByText("dsa.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm delete" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledTimes(2));
    expect(mocks.remove).toHaveBeenLastCalledWith("/api/v1/sources", { params: { query: { key: "dsa.pdf" } } });
  });
  it("announces a deletion and moves focus to the next source", async () => {
    const other = { ...document, source_key: "graphs.pdf", docs: ["graphs.pdf"] };
    mocks.get.mockResolvedValueOnce({ data: { documents: [document, other] } }).mockResolvedValue({ data: { documents: [other] } });
    renderTable(false);
    fireEvent.click(await screen.findByRole("button", { name: "Delete dsa.pdf" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByText("Deleted dsa.pdf and its indexed passages.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Delete graphs.pdf" })).toHaveFocus());
  });
  it("focuses the heading after deleting the last source", async () => {
    mocks.get.mockResolvedValueOnce({ data: { documents: [document] } }).mockResolvedValue({ data: { documents: [] } });
    renderTable(false);
    fireEvent.click(await screen.findByRole("button", { name: "Delete dsa.pdf" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Indexed sources" })).toHaveFocus());
  });
  it("filters locally and can recover from no results", async () => {
    renderTable(true);
    await screen.findByText("dsa.pdf");
    fireEvent.change(screen.getByRole("searchbox", { name: "Filter indexed sources" }), { target: { value: "missing" } });
    expect(screen.queryByText("dsa.pdf")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Clear filter" }));
    expect(screen.getByText("dsa.pdf")).toBeInTheDocument();
    expect(mocks.get).toHaveBeenCalledTimes(1);
  });
  it("offers a real query retry after a library fetch failure", async () => {
    mocks.get.mockRejectedValueOnce(new Error("Library unavailable"));
    renderTable(true);
    expect(await screen.findByRole("alert")).toHaveTextContent("Library unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Retry loading sources" }));
    expect(await screen.findByText("dsa.pdf")).toBeInTheDocument();
    expect(mocks.get).toHaveBeenCalledTimes(2);
  });
});
