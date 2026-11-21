import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const nav = vi.hoisted(() => ({ pathname: "/ask" }));
const health = vi.hoisted(() => ({ status: 200 }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname, useRouter: () => ({ push: vi.fn() }) }));
vi.hoisted(() => {
  // The API client keeps a reference to fetch from import time, so stub it first.
  globalThis.fetch = (async () =>
    health.status === 200
      ? Response.json({ status: "ok", version: "1.0.0", semantic_search: false, chunks: 2 })
      : Response.json({ error: { code: "rate_limited", message: "Rate limit exceeded" } }, { status: health.status })) as typeof fetch;
});

import { DemoContext } from "@/lib/demo";
import { AppShell, DEMO_STRIP_KEY } from "./app-shell";

function renderShell(demo = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(
    <DemoContext.Provider value={demo}>
      <QueryClientProvider client={client}><AppShell><h1>Page</h1></AppShell></QueryClientProvider>
    </DemoContext.Provider>,
  ) };
}

beforeEach(() => {
  nav.pathname = "/ask";
  health.status = 200;
  delete document.documentElement.dataset.demoStrip;
  localStorage.clear();
});

describe("AppShell", () => {
  it("marks the open page and, on a section's other pages, the section", () => {
    const { rerender, client } = renderShell();
    const main = () => screen.getByRole("navigation", { name: "Main" });
    expect(within(main()).getByRole("link", { name: "Ask" })).toHaveAttribute("aria-current", "page");
    nav.pathname = "/math";
    rerender(<QueryClientProvider client={client}><AppShell><h1>Page</h1></AppShell></QueryClientProvider>);
    expect(within(main()).getByRole("link", { name: "Tools" })).toHaveAttribute("aria-current", "true");
    expect(within(main()).getByRole("link", { name: "Ask" })).not.toHaveAttribute("aria-current");
    const bar = screen.getByRole("navigation", { name: "Tools pages" });
    expect(within(bar).getAllByRole("link").map((l) => l.textContent)).toEqual(["Concept map", "Compare sources", "Agent", "Math"]);
    expect(within(bar).getByRole("link", { name: "Math" })).toHaveAttribute("aria-current", "page");
    expect(within(main()).getByRole("link", { name: "Tools" })).toHaveAttribute("href", "/concept-map");
  });

  it("puts the map and insights in Library and the guided tools in Practice", () => {
    const { rerender, client } = renderShell();
    const again = () => rerender(<QueryClientProvider client={client}><AppShell><h1>Page</h1></AppShell></QueryClientProvider>);
    const main = () => screen.getByRole("navigation", { name: "Main" });
    nav.pathname = "/visualize";
    again();
    expect(within(main()).getByRole("link", { name: "Library" })).toHaveAttribute("aria-current", "true");
    const library = screen.getByRole("navigation", { name: "Library pages" });
    expect(within(library).getAllByRole("link").map((l) => l.textContent)).toEqual(["Sources", "Map", "Insights"]);
    expect(within(library).getByRole("link", { name: "Map" })).toHaveAttribute("aria-current", "page");
    nav.pathname = "/work-it-out";
    again();
    expect(within(main()).getByRole("link", { name: "Practice" })).toHaveAttribute("aria-current", "true");
    const practice = screen.getByRole("navigation", { name: "Practice pages" });
    expect(within(practice).getAllByRole("link").map((l) => l.textContent)).toEqual(["Flashcards", "LeetCode", "Work it out", "Explain at my level"]);
    expect(within(practice).getByRole("link", { name: "Work it out" })).toHaveAttribute("aria-current", "page");
    nav.pathname = "/concept-map";
    again();
    expect(within(main()).getByRole("link", { name: "Tools" })).toHaveAttribute("aria-current", "page");
  });

  it("describes the index in plain words, readable at every width", async () => {
    renderShell();
    expect(await screen.findByText("2 passages indexed · keyword search")).toBeInTheDocument();
    // Coming online first is not announced; nothing re-announces on later polls.
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("announces when the service is busy", async () => {
    health.status = 429;
    renderShell();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/Service busy/));
    expect(screen.getByText("Service busy · retrying shortly")).toBeInTheDocument();
  });

  it("shows no demo notice outside the demo", () => {
    renderShell(false);
    expect(screen.queryByRole("region", { name: "About this demo" })).toBeNull();
  });

  it("shows a dismissible demo notice on the public demo and remembers the choice", async () => {
    renderShell(true);
    const strip = screen.getByRole("region", { name: "About this demo" });
    expect(strip).toHaveTextContent("Public demo");
    expect(within(strip).getByRole("link", { name: "Source code" })).toHaveAttribute("href", "https://github.com/moh0405/Lectern");
    expect(within(strip).getByRole("link", { name: "How it works" })).toHaveAttribute("href", "https://github.com/moh0405/Lectern#readme");
    within(strip).getByRole("button", { name: "Hide the demo notice" }).focus();
    await act(() => userEvent.keyboard("{Enter}"));
    expect(document.documentElement.dataset.demoStrip).toBe("dismissed");
    expect(localStorage.getItem(DEMO_STRIP_KEY)).toBe("1");
    expect(document.getElementById("workspace-content")).toHaveFocus();
  });
});
