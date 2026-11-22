import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useQuery } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const nav = vi.hoisted(() => ({ pathname: "/ask" }));
const health = vi.hoisted(() => ({ status: 200, starting: false, calls: 0 }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname, useRouter: () => ({ push: vi.fn() }) }));
vi.hoisted(() => {
  // The API client keeps a reference to fetch from import time, so stub it first.
  globalThis.fetch = (async () => {
    health.calls += 1;
    return health.starting ? Response.json({ status: "starting", version: "1.0.0", semantic_search: null, chunks: null }) : health.status === 200
      ? Response.json({ status: "ok", version: "1.0.0", semantic_search: false, chunks: 2 })
      : Response.json({ error: { code: "rate_limited", message: "Rate limit exceeded" } }, { status: health.status });
  }) as typeof fetch;
});

import { DemoContext } from "@/lib/demo";
import { AppShell, DEMO_STRIP_KEY } from "./app-shell";

function renderShell(demo = false, page: React.ReactNode = <h1>Page</h1>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(
    <DemoContext.Provider value={demo}>
      <QueryClientProvider client={client}><AppShell>{page}</AppShell></QueryClientProvider>
    </DemoContext.Provider>,
  ) };
}

beforeEach(() => {
  nav.pathname = "/ask";
  health.status = 200;
  health.starting = false;
  health.calls = 0;
  delete document.documentElement.dataset.demoStrip;
  localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

const statusText = () => document.querySelector(".api-status-text")?.textContent;
const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

/** A page that reads the passage count, like Ask's source margin. */
const statsCalls = { n: 0 };
function StatsPage() {
  const q = useQuery({ queryKey: ["stats"], queryFn: async () => { statsCalls.n += 1; if (health.status !== 200) throw new Error("down"); return 1; } });
  return <p>{q.isError ? "stats failed" : q.isSuccess ? "stats loaded" : "stats loading"}</p>;
}

describe("API status while the service wakes up", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"] });
  });

  it("keeps saying Starting up through a cold start, re-checks quickly, and refreshes pages once it is back", async () => {
    health.status = 503;
    statsCalls.n = 0;
    renderShell(false, <StatsPage />);
    await advance(100);
    expect(statusText()).toBe("Starting up…");
    expect(screen.getByText("stats failed")).toBeInTheDocument();
    const seen = new Set<string>();
    for (let t = 0; t < 40_000; t += 1_000) {
      await advance(1_000);
      seen.add(statusText() ?? "");
    }
    expect([...seen]).toEqual(["Starting up…"]);
    expect(health.calls).toBeGreaterThanOrEqual(8); // backoff, not a 30 s poll
    health.status = 200;
    await advance(10_000); // the backoff is capped at 10 s
    expect(statusText()).toBe("2 passages indexed · keyword search");
    expect(screen.getByRole("status")).toHaveTextContent("Connected to the study service again");
    await advance(100);
    expect(screen.getByText("stats loaded")).toBeInTheDocument();
    expect(statsCalls.n).toBe(2);
  });

  it("says Offline only after the cold-start window, keeps checking, and recovers by itself", async () => {
    health.status = 503;
    renderShell();
    await advance(59_000);
    expect(statusText()).toBe("Starting up…");
    await advance(11_000);
    expect(statusText()).toBe("Offline");
    expect(screen.getByRole("status")).toHaveTextContent("Offline: the study service cannot be reached.");
    const calls = health.calls;
    await advance(30_000);
    expect(health.calls - calls).toBe(2); // slower, but still checking
    health.status = 200;
    await advance(15_000);
    expect(statusText()).toBe("2 passages indexed · keyword search");
    const after = health.calls;
    await advance(25_000);
    expect(health.calls).toBe(after); // back to the slow healthy poll
  });

  it("checks again at once when the browser comes back online", async () => {
    health.status = 503;
    renderShell();
    await advance(100);
    const calls = health.calls;
    health.status = 200;
    await act(async () => { window.dispatchEvent(new Event("online")); });
    await advance(10);
    expect(health.calls).toBe(calls + 1);
    expect(statusText()).toBe("2 passages indexed · keyword search");
  });

  it("checks again at once on window focus while not healthy", async () => {
    health.status = 503;
    renderShell();
    await advance(100);
    const calls = health.calls;
    health.status = 200;
    await act(async () => { window.dispatchEvent(new Event("focus")); });
    await advance(10);
    expect(health.calls).toBe(calls + 1);
    expect(statusText()).toBe("2 passages indexed · keyword search");
  });
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

  it("shows a calm starting state, without an invented passage count", async () => {
    health.starting = true;
    renderShell();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/starting up/));
    expect(screen.getByText("Starting up…")).toBeInTheDocument();
    expect(screen.queryByText(/passage/)).toBeNull();
    expect(screen.queryByText("Offline")).toBeNull();
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
