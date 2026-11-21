import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { CommandPalette, scoreItem } from "./command-palette";

// cmdk measures the DOM with APIs jsdom lacks
beforeEach(() => {
  push.mockReset();
  delete document.documentElement.dataset.theme;
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  Element.prototype.scrollIntoView ??= () => {};
});

function Shell() {
  return (
    <>
      <CommandPalette />
      <main id="workspace-content" tabIndex={-1}>content</main>
    </>
  );
}

const openWithKeys = async () => {
  await userEvent.keyboard("{Control>}k{/Control}");
  return screen.findByPlaceholderText(/Go to a page/);
};
const options = () => screen.getAllByRole("option").map((o) => o.textContent);

describe("CommandPalette", () => {
  it("opens with Ctrl+K and closes with Escape, returning focus to the opener", async () => {
    render(<Shell />);
    expect(screen.queryByRole("dialog")).toBeNull();
    const trigger = screen.getByRole("button", { name: "Find a page or tool" });
    await userEvent.click(trigger);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("filters, and Enter navigates to the highlighted entry and focuses the main region", async () => {
    render(<Shell />);
    await userEvent.type(await openWithKeys(), "leetc");
    expect(screen.getByText("LeetCode")).toBeInTheDocument();
    expect(screen.queryByText("Analytics")).toBeNull();
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith("/leetcode");
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(document.getElementById("workspace-content")).toHaveFocus());
  });

  it("keeps the exact jumps people rely on", async () => {
    render(<Shell />);
    await userEvent.type(await openWithKeys(), "math");
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenLastCalledWith("/math");
    await userEvent.type(await openWithKeys(), "socratic");
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenLastCalledWith("/tutor?tool=socratic");
    await userEvent.type(await openWithKeys(), "eli5");
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenLastCalledWith("/tutor?tool=adaptive");
  });

  it("groups everything under the four sections and names Sources as the Library", async () => {
    render(<Shell />);
    await openWithKeys();
    const dialog = screen.getByRole("dialog");
    for (const heading of ["Ask", "Library", "Practice", "Tools", "Actions"]) expect(within(dialog).getAllByText(heading, { selector: "[cmdk-group-heading]" })).toHaveLength(1);
    expect(screen.getByRole("option", { name: /Library \(Sources\)/ })).toBeInTheDocument();
  });

  it("finds pages by section names and synonyms, without fuzzy false matches", async () => {
    render(<Shell />);
    const input = await openWithKeys();
    await userEvent.type(input, "library");
    expect(options()[0]).toContain("Library (Sources)");
    await userEvent.clear(input);
    await userEvent.type(input, "practice");
    expect(options()).toEqual(expect.arrayContaining([expect.stringContaining("Flashcards"), expect.stringContaining("LeetCode")]));
    expect(options().some((o) => o?.includes("Compare sources"))).toBe(false);
    await userEvent.clear(input);
    await userEvent.type(input, "theme");
    expect(options().some((o) => o?.includes("Compare sources"))).toBe(false);
    expect(options()[0]).toBe("Switch to light theme");
  });

  it("switches the theme from the palette and returns focus", async () => {
    render(<Shell />);
    const trigger = screen.getByRole("button", { name: "Find a page or tool" });
    await userEvent.click(trigger);
    await userEvent.type(await screen.findByPlaceholderText(/Go to a page/), "dark");
    await userEvent.keyboard("{Enter}");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(push).not.toHaveBeenCalled();
    await waitFor(() => expect(trigger).toHaveFocus());
    await userEvent.type(await openWithKeys(), "theme");
    expect(options()[0]).toBe("Switch to dark theme");
  });

  it("offers to add material and to ask whatever was typed", async () => {
    render(<Shell />);
    const input = await openWithKeys();
    await userEvent.type(input, "add material");
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenLastCalledWith("/sources");

    await userEvent.type(await openWithKeys(), "what is a heap?");
    expect(await screen.findByText(/Nothing matches/)).toBeInTheDocument();
    expect(options()).toEqual(["Ask: what is a heap?"]);
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenLastCalledWith("/ask?q=what%20is%20a%20heap%3F");
  });
});

describe("scoreItem", () => {
  it("needs every typed word to start a word of the label or a keyword", () => {
    expect(scoreItem({ label: "Compare sources", keywords: ["synthesis"] }, "practice")).toBe(0);
    expect(scoreItem({ label: "Flashcards", keywords: ["practice"] }, "prac")).toBeGreaterThan(0);
    expect(scoreItem({ label: "Math" }, "math")).toBeGreaterThan(scoreItem({ label: "Tutor tools", keywords: ["math"] }, "math"));
    expect(scoreItem({ label: "Math" }, "")).toBe(1);
  });
});
