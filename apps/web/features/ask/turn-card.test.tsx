import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as rtlRender, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const post = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { http: { POST: (...a: unknown[]) => post(...a) } },
  unwrap: (r: { data?: unknown; error?: unknown }) => {
    if (r.error !== undefined) throw new Error("server said no");
    return r.data;
  },
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : "unknown"),
}));

import { TurnCard } from "./turn-card";
import type { Turn } from "./session";

const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const render = (ui: React.ReactElement) =>
  rtlRender(ui, { wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });

const turn = (over: Partial<Turn>): Turn => ({ id: "1", question: "what is a heap", answer: "", chunks: [], status: "done", ...over });
const chunks = [{ text: "heap text", doc: "heaps.pdf", page: 1, score: 0.7 }];

describe("TurnCard", () => {
  it("explains a missing API key and still shows the retrieved sources", () => {
    render(
      <TurnCard
        turn={turn({ status: "error", chunks, error: { code: "llm_unavailable", message: "GEMINI_API_KEY is not set" } })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/no language-model key/i);
    expect(screen.getByText("Sources (1)")).toBeInTheDocument();
    expect(screen.getByRole("article")).toHaveTextContent("heap text");
  });

  it("shows other errors as alerts", () => {
    render(<TurnCard turn={turn({ status: "error", error: { code: "llm_error", message: "upstream exploded" } })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("upstream exploded");
  });

  it("offers Stop while streaming and remove when finished", async () => {
    const onStop = vi.fn();
    const onRemove = vi.fn();
    const { rerender } = render(<TurnCard turn={turn({ status: "streaming", answer: "Par" })} onStop={onStop} onRemove={onRemove} />);
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalled();
    rerender(<TurnCard turn={turn({ answer: "Done." })} onStop={onStop} onRemove={onRemove} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onRemove).toHaveBeenCalled();
  });

  it("renders markdown answers without executing raw HTML", () => {
    const { container } = render(
      <TurnCard turn={turn({ answer: "**bold** <img src=x onerror=alert(1)> <script>alert(1)</script>" })} onStop={() => {}} onRemove={() => {}} />,
    );
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(container.querySelector("img, script")).toBeNull();
  });

  it("says when nothing matched", () => {
    render(<TurnCard turn={turn({ answer: "I could not find that.", chunks: [] })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByText(/No matching passages/)).toBeInTheDocument();
  });
});


describe("TurnCard citation checks", () => {
  const done = (over: Partial<Turn>) => turn({ answer: "A heap is a tree.", ...over });

  it("warns about citations to sources the model was not given", () => {
    render(
      <TurnCard
        turn={done({
          citations: [
            { label: "heaps.pdf (page 1)", doc: "heaps.pdf", page: 1, status: "ok" },
            { label: "Invented.pdf (page 9)", doc: "Invented.pdf", page: 9, status: "unknown_source" },
            { label: "heaps.pdf (page 40)", doc: "heaps.pdf", page: 40, status: "page_not_retrieved" },
          ],
        })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    const note = screen.getByRole("status");
    expect(note).toHaveTextContent("cites things it was not given");
    expect(note).toHaveTextContent("[Invented.pdf (page 9)]");
    expect(note).toHaveTextContent("that source was not among the passages");
    expect(note).toHaveTextContent("[heaps.pdf (page 40)]");
    expect(note).toHaveTextContent("that page was not among the passages");
    expect(note).not.toHaveTextContent("[heaps.pdf (page 1)]");
  });

  it("says nothing when every citation checks out", () => {
    render(
      <TurnCard
        turn={done({ citations: [{ label: "heaps.pdf (page 1)", doc: "heaps.pdf", page: 1, status: "ok" }] })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("notes an answer that cites none of its sources", () => {
    render(<TurnCard turn={done({ uncited: true, citations: [] })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("does not cite any of the sources");
  });

  it("does not judge an answer that is still streaming", () => {
    render(
      <TurnCard
        turn={done({ status: "streaming", citations: [{ label: "x.pdf", doc: "x.pdf", page: null, status: "unknown_source" }] })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("shows a cached badge and offers a fresh answer", async () => {
    const onFresh = vi.fn();
    const { rerender } = render(<TurnCard turn={done({ cached: true })} onStop={() => {}} onRemove={() => {}} onFresh={onFresh} />);
    expect(screen.getByText("cached")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fresh answer" }));
    expect(onFresh).toHaveBeenCalled();
    rerender(<TurnCard turn={done({ cached: false })} onStop={() => {}} onRemove={() => {}} onFresh={onFresh} />);
    expect(screen.queryByText("cached")).toBeNull();
    expect(screen.queryByRole("button", { name: "Fresh answer" })).toBeNull();
  });

  it("saves a finished answer as a flashcard", async () => {
    post.mockResolvedValue({ data: { id: 1 } });
    render(<TurnCard turn={turn({ answer: "A **heap** is a tree.", chunks })} onStop={() => {}} onRemove={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Save as flashcard" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Saved as flashcard" })).toBeDisabled());
    expect(post).toHaveBeenCalledWith("/api/v1/cards", { body: { front: "what is a heap", back: "A heap is a tree.", source: "heaps.pdf" } });
  });

  it("does not offer to save an unfinished or empty answer", () => {
    render(<TurnCard turn={turn({ status: "streaming", answer: "partial" })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.queryByRole("button", { name: /flashcard/i })).toBeNull();
  });
});

describe("TurnCard for agentic answers", () => {
  const steps = [
    { name: "rewrite", detail: "Searching for: binary heap priority queue" },
    { name: "grade", detail: "Passages look sufficient" },
  ];

  it("lists what the workflow did and what it cost", () => {
    render(<TurnCard turn={turn({ agent: true, steps, llmCalls: 3, answer: "A heap is a tree.", chunks })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByText("agentic")).toBeInTheDocument();
    expect(screen.getByText(/How it answered \(2 steps, 3 model calls\)/)).toBeInTheDocument();
    expect(screen.getByText("Searching for: binary heap priority queue")).toBeInTheDocument();
  });

  it("says when the first answer was rewritten", () => {
    render(<TurnCard turn={turn({ agent: true, steps, rewritten: true, answer: "ok", chunks })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByText(/cited sources it was not given, so it was rewritten/)).toBeInTheDocument();
  });

  it("shows nothing extra for a plain answer", () => {
    render(<TurnCard turn={turn({ answer: "ok", chunks })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.queryByText(/How it answered/)).toBeNull();
    expect(screen.queryByText("agentic")).toBeNull();
  });
});


describe("TurnCard clipboard recovery", () => {
  it("explains how to copy an answer when clipboard permission is denied", async () => {
    const user = userEvent.setup();
    const write = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockRejectedValue(new Error("Permission denied"));
    render(
      <TurnCard
        turn={turn({ answer: "A heap is a tree." })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Copy answer" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Select the answer text to copy it manually",
    );
    expect(
      screen.getByRole("button", { name: "Copy answer" }),
    ).toHaveAccessibleDescription(/Copy is unavailable/);
    expect(screen.getByText("A heap is a tree.")).toBeInTheDocument();
    write.mockRestore();
  });
});

describe("retry after a failed answer", () => {
  it("keeps the original question visible and retries only when requested", async () => {
    const onFresh=vi.fn();
    render(<TurnCard turn={turn({status:"error",error:{code:"rate_limited",message:"Wait about a minute, then try again."}})} onStop={()=>{}} onRemove={()=>{}} onFresh={onFresh} />);
    expect(screen.getByRole("heading",{name:"what is a heap"})).toBeInTheDocument();
    expect(onFresh).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button",{name:"Try this question again"}));
    expect(onFresh).toHaveBeenCalledTimes(1);
  });
  it("disables another retry while a question is running", () => {
    render(<TurnCard turn={turn({status:"error",error:{code:"rate_limited",message:"Wait before retrying."}})} onStop={()=>{}} onRemove={()=>{}} onFresh={()=>{}} busy />);
    expect(screen.getByRole("button",{name:"Try this question again"})).toBeDisabled();
  });
});
