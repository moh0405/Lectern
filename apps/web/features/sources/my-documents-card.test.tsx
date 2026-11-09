import "fake-indexeddb/auto";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ extract: vi.fn(), remove: vi.fn(), save: vi.fn(), embed: vi.fn(), docs: vi.fn() }));
vi.mock("@/lib/browser-rag/use-local-docs", () => ({ LOCAL_DOCS_KEY: ["local-docs"], useLocalDocs: mocks.docs }));
vi.mock("@/lib/browser-rag/extract", () => ({ ACCEPT: ".pdf,.txt,.md", MAX_FILE_MB: 100, extractPages: mocks.extract }));
vi.mock("@/lib/browser-rag/store", () => ({ deleteDoc: mocks.remove, saveDoc: mocks.save, newDocId: () => "local-new" }));
vi.mock("@/lib/browser-rag/embed", () => ({ EMBEDDING_DIM: 3, loadEmbedder: vi.fn(), embeddingsEnabled: () => false, embedTexts: mocks.embed }));
import { MyDocumentsCard } from "./my-documents-card";
const existing = { id: "local-one", name: "notes.md", addedAt: 1, pages: 1, passages: [{ text: "Graph notes", page: 1 }], vectors: null, dim: 3 };
function renderCard() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MyDocumentsCard /></QueryClientProvider>); }
beforeEach(() => {
  mocks.docs.mockReset().mockReturnValue({ data: [existing], isPending: false });
  mocks.remove.mockReset().mockResolvedValue(undefined);
  mocks.save.mockReset().mockResolvedValue(undefined);
  mocks.extract.mockReset().mockResolvedValue(["A graph has vertices and edges. ".repeat(20)]);
  mocks.embed.mockReset().mockResolvedValue(null);
});
afterEach(() => vi.unstubAllGlobals());
describe("browser-local documents", () => {
  it("explains unsupported browser storage without offering an unusable upload", () => {
    vi.stubGlobal("indexedDB", undefined);
    renderCard();
    expect(screen.getByRole("alert")).toHaveTextContent("does not support the document storage");
    expect(screen.getByRole("button", { name: "Choose files" })).toBeDisabled();
  });
  it("shows the real local limit and distinguishes model passage sharing", () => {
    renderCard();
    expect(screen.getByText(/up to 100 MB per file/)).toBeInTheDocument();
    expect(screen.getByText(/only matching passages are sent/)).toBeInTheDocument();
    expect(screen.getByText(/Clearing browser data removes them/)).toBeInTheDocument();
  });
  it("asks for confirmation before removing a local document", async () => {
    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Remove notes.md" }));
    expect(mocks.remove).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Confirm remove" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mocks.remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Remove notes.md" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm remove" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith("local-one"));
  });
  it("keeps removal failures recoverable", async () => {
    mocks.remove.mockRejectedValueOnce(new Error("Storage blocked"));
    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Remove notes.md" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm remove" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not been marked as removed");
    expect(screen.getByText("notes.md")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm remove" })).toBeEnabled();
  });
  it("does not save unsupported input and enables choosing a replacement", async () => {
    mocks.extract.mockRejectedValueOnce(new Error("only PDF, TXT and Markdown files work here"));
    renderCard();
    fireEvent.change(await screen.findByLabelText("Add my documents"), { target: { files: [new File(["image"], "photo.png")] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("only PDF, TXT and Markdown");
    expect(mocks.save).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Choose files" })).toBeEnabled();
  });
  it("saves genuine extracted passages and announces completion after storage succeeds", async () => {
    renderCard();
    fireEvent.change(await screen.findByLabelText("Add my documents"), { target: { files: [new File(["notes"], "new.md")] } });
    await waitFor(() => expect(mocks.save).toHaveBeenCalled());
    const saved = mocks.save.mock.calls[0]?.[0];
    expect(saved).toMatchObject({ id: "local-new", name: "new.md", vectors: null });
    expect(saved?.passages.length).toBeGreaterThan(0);
    expect(await screen.findByText(/1 document added to this browser/)).toBeInTheDocument();
  });
});
