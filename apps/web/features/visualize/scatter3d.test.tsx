import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { groupByDoc, Scatter3D } from "./scatter3d";

const pt = (doc: string, index: number) => ({ x: 0, y: 0, z: 0, doc, page: 1, text: "t", index });

describe("groupByDoc", () => {
  it("groups by document in first-seen order, keeping every point", () => {
    const groups = groupByDoc([pt("a.pdf", 0), pt("b.pdf", 1), pt("a.pdf", 2)]);
    expect([...groups.keys()]).toEqual(["a.pdf", "b.pdf"]);
    expect(groups.get("a.pdf")!.map((p) => p.index)).toEqual([0, 2]);
    expect(groups.get("b.pdf")).toHaveLength(1);
  });
  it("handles no points", () => {
    expect(groupByDoc([]).size).toBe(0);
  });
});

describe("Scatter3D without WebGL", () => {
  it("explains itself instead of drawing a blank box", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    render(<Scatter3D points={[pt("a.pdf", 0)]} onSelect={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent(/cannot draw WebGL/i);
    expect(screen.queryByTestId("scatter3d")).toBeNull();
  });
});
