import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { DemoContext } from "@/lib/demo";
import { LlmError } from "./llm-error";

const noKey = new ApiError(503, "llm_unavailable", "GEMINI_API_KEY is not set");

describe("LlmError", () => {
  it("explains a switched-off model calmly, with the technical detail tucked away", () => {
    render(<LlmError error={noKey} />);
    const note = screen.getByRole("status");
    expect(note).toHaveTextContent("Answers are switched off");
    expect(note).toHaveTextContent("you can still search your sources");
    expect(screen.getByText("Technical details")).toBeInTheDocument();
    expect(screen.queryByText(/Set it in/)).toBeNull();
  });

  it("leaves server details out on the public demo", () => {
    render(<DemoContext.Provider value><LlmError error={noKey} /></DemoContext.Provider>);
    expect(screen.queryByText("Technical details")).toBeNull();
    expect(screen.getByRole("status")).not.toHaveTextContent("GEMINI");
  });

  it("titles real failures as alerts and offers a retry", async () => {
    const onRetry = vi.fn();
    render(<LlmError error={new ApiError(500, "internal_error", "Internal server error")} onRetry={onRetry} retryLabel="Try this again" />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Server error");
    expect(alert).toHaveTextContent("Something went wrong on the server");
    await userEvent.click(screen.getByRole("button", { name: "Try this again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
