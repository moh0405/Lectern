import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ErrorPage from "./error";

describe("route error boundary", () => {
  it("focuses its heading, and drops cached data before retrying", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const client = new QueryClient();
    client.setQueryData(["documents"], { malformed: true });
    client.setQueryData(["health"], { status: "ok" });
    const retry = vi.fn(() => {
      // By the time the segment re-renders, the bad data must be gone.
      expect(client.getQueryData(["documents"])).toBeUndefined();
    });
    render(<QueryClientProvider client={client}><ErrorPage error={new Error("boom")} retry={retry} /></QueryClientProvider>);

    const heading = screen.getByRole("heading", { level: 1, name: "Something went wrong" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByRole("link", { name: "Go to Ask" })).toHaveAttribute("href", "/ask");
    expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
    expect(screen.getByText("Error")).toHaveClass("eyebrow");

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
    expect(client.getQueryData(["health"])).toEqual({ status: "ok" }); // the shell's status check is kept
  });
});
