import { describe, expect, it } from "vitest";
import { connectionText, edgesOf, layoutGraph, nodeAriaLabel, toDot } from "./graph-layout";

const nodes = [
  { id: "a", label: "Array" },
  { id: "b", label: "Hash Table" },
  { id: "c", label: "Two Sum" },
];
const edges = [
  { from: "a", to: "c", label: "used by" },
  { from: "b", to: "c" },
  { from: "ghost", to: "c" },
];

describe("layoutGraph", () => {
  it("positions every node, flows left to right and keeps nodes apart", () => {
    const out = layoutGraph(nodes, edges);
    expect(out.map((n) => n.id)).toEqual(["a", "b", "c"]);
    const [a, b, c] = out;
    expect(c!.x).toBeGreaterThan(a!.x); // targets sit to the right of their sources
    expect(a!.x).toBe(b!.x); // same rank
    expect(a!.y).not.toBe(b!.y); // siblings do not overlap
    for (const n of out) expect(Number.isFinite(n.x) && Number.isFinite(n.y)).toBe(true);
  });
  it("handles an empty graph and edges to unknown nodes", () => {
    expect(layoutGraph([], [])).toEqual([]);
    expect(() => layoutGraph(nodes, [{ from: "x", to: "y" }])).not.toThrow();
  });
});

describe("text alternatives", () => {
  it("names connections with labels and counts them for screen readers", () => {
    expect(connectionText(edges[0]!, nodes)).toBe("Array → used by → Two Sum");
    expect(connectionText(edges[1]!, nodes)).toBe("Hash Table → related to → Two Sum");
    expect(edgesOf("c", edges)).toHaveLength(3);
    expect(nodeAriaLabel(nodes[0]!, edges)).toBe("Array, 1 connection. Press Enter to show it.");
    expect(nodeAriaLabel(nodes[2]!, edges)).toBe("Two Sum, 3 connections. Press Enter to show them.");
    expect(nodeAriaLabel({ id: "z", label: "Alone" }, edges)).toBe("Alone, no connections.");
  });
});

describe("toDot", () => {
  it("emits valid DOT and escapes quotes and backslashes", () => {
    const dot = toDot([{ id: 'say "hi"', label: "a\\b" }, { id: "n", label: "N" }], [{ from: 'say "hi"', to: "n" }]);
    expect(dot.startsWith("digraph G {")).toBe(true);
    expect(dot).toContain('"say \\"hi\\"" [label="a\\\\b"];');
    expect(dot).toContain('"say \\"hi\\"" -> "n" [label="related"];');
    expect(dot.trimEnd().endsWith("}")).toBe(true);
  });
});
