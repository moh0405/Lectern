import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { CommandPalette } from "./command-palette";

// cmdk measures the DOM with APIs jsdom lacks
beforeEach(() => {
  push.mockReset();
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  Element.prototype.scrollIntoView ??= () => {};
});

describe("CommandPalette", () => {
  it("opens with Ctrl+K and closes with Escape", async () => {
    render(<CommandPalette />);
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.keyboard("{Control>}k{/Control}");
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("filters, and Enter navigates to the highlighted entry", async () => {
    render(<CommandPalette />);
    await userEvent.keyboard("{Meta>}k{/Meta}");
    await userEvent.type(await screen.findByPlaceholderText(/Go to a page/), "leetc");
    expect(screen.getByText("LeetCode")).toBeInTheDocument();
    expect(screen.queryByText("Analytics")).toBeNull();
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith("/leetcode");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("finds tools by keyword and says when nothing matches", async () => {
    render(<CommandPalette />);
    await userEvent.click(screen.getByRole("button", { name: /Jump to/ }));
    const input = await screen.findByPlaceholderText(/Go to a page/);
    await userEvent.type(input, "eli5");
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith("/tutor?tool=adaptive");

    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.type(await screen.findByPlaceholderText(/Go to a page/), "zzzzqq");
    expect(await screen.findByText("Nothing matches.")).toBeInTheDocument();
  });
});
