import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { Segmented } from "./segmented";

function Harness() {
  const [v, setV] = useState<"a" | "b" | "c">("a");
  return (
    <>
      <Segmented legend="Approach" name="approach" value={v} onChange={setV} options={[{ value: "a", label: "Answer" }, { value: "b", label: "Guided", description: "Hints first" }, { value: "c", label: "Try first" }]} />
      <p data-testid="value">{v}</p>
    </>
  );
}

describe("Segmented", () => {
  it("is a labelled radio group that arrow keys and clicks move through", async () => {
    render(<Harness />);
    const group = screen.getByRole("group", { name: "Approach" });
    expect(group).toBeInTheDocument();
    const answer = screen.getByRole("radio", { name: "Answer" });
    expect(answer).toBeChecked();
    expect(screen.getByRole("radio", { name: "Guided" })).toHaveAccessibleDescription("Hints first");
    await userEvent.tab();
    expect(answer).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "Guided" })).toBeChecked();
    expect(screen.getByTestId("value")).toHaveTextContent("b");
    await userEvent.click(screen.getByText("Try first"));
    expect(screen.getByRole("radio", { name: "Try first" })).toBeChecked();
  });
});
