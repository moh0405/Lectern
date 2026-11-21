import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { http: { GET: async () => ({ data: { documents: [] } }), POST: (...args: unknown[]) => post(...args) } },
  unwrap: (r: { data?: unknown }) => r.data,
}));
const url = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(url.search) }));

import { AdaptiveFromUrl } from "./adaptive";
import { ConceptMapFromUrl } from "./concept-map";
import { SocraticFromUrl } from "./socratic";
import { SynthesisFromUrl } from "./synthesis";

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>);

beforeEach(() => {
  post.mockReset();
  url.search = "";
});

describe("tool pages prefill from the URL", () => {
  it("fills the concept map and compare topics from ?topic=, without running anything", () => {
    url.search = "?topic=%20Binary%20heaps%20";
    wrap(<ConceptMapFromUrl />);
    expect(screen.getByLabelText("Topic")).toHaveValue("Binary heaps");
    wrap(<SynthesisFromUrl />);
    expect(screen.getByLabelText(/Topic to compare/)).toHaveValue("Binary heaps");
    expect(post).not.toHaveBeenCalled();
  });

  it("caps a topic at the field's 200 characters", () => {
    url.search = `?topic=${"a".repeat(300)}`;
    wrap(<ConceptMapFromUrl />);
    expect((screen.getByLabelText("Topic") as HTMLInputElement).value).toHaveLength(200);
  });

  it("fills Work it out and Explain from ?question=", () => {
    url.search = "?question=Why%20is%20binary%20search%20O(log%20n)%3F";
    wrap(<SocraticFromUrl />);
    expect(screen.getByLabelText("What are you trying to work out?")).toHaveValue("Why is binary search O(log n)?");
    wrap(<AdaptiveFromUrl />);
    expect(screen.getByLabelText("Question")).toHaveValue("Why is binary search O(log n)?");
    expect(post).not.toHaveBeenCalled();
  });

  it("starts empty without a parameter", () => {
    wrap(<SocraticFromUrl />);
    expect(screen.getByLabelText("What are you trying to work out?")).toHaveValue("");
  });
});
