import { describe, expect, it } from "vitest";
import { legacyTutorTarget } from "./tutor-redirect";

const target = (qs: string) => legacyTutorTarget(new URLSearchParams(qs));

describe("legacyTutorTarget", () => {
  it("sends each old tool tab to its own page without the tool parameter", () => {
    expect(target("tool=map")).toBe("/concept-map");
    expect(target("tool=socratic")).toBe("/work-it-out");
    expect(target("tool=synthesis")).toBe("/compare");
    expect(target("tool=adaptive")).toBe("/explain");
  });

  it("keeps the other parameters", () => {
    expect(target("tool=synthesis&topic=Heaps")).toBe("/compare?topic=Heaps");
    expect(target("topic=Binary+trees&tool=map")).toBe("/concept-map?topic=Binary+trees");
    expect(target("tool=socratic&question=Why%3F")).toBe("/work-it-out?question=Why%3F");
  });

  it("falls back to the concept map for no tool or an unknown one", () => {
    expect(target("")).toBe("/concept-map");
    expect(target("tool=nope&topic=x")).toBe("/concept-map?topic=x");
    expect(target("tool=toString")).toBe("/concept-map");
    expect(target("tool=map&tool=adaptive")).toBe("/concept-map");
  });
});
