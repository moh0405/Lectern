import { expect, it } from "vitest";
import { pageLabel, plural } from "./format";

it("pluralizes and formats numbers", () => {
  expect(plural(0, "chunk")).toBe("0 chunks");
  expect(plural(1, "chunk")).toBe("1 chunk");
  expect(plural(1234, "chunk")).toBe("1,234 chunks");
  expect(plural(2, "match", "matches")).toBe("2 matches");
});

it("labels a page or a page range", () => {
  expect(pageLabel(132)).toBe("page 132");
  expect(pageLabel(132, 133)).toBe("pages 132–133");
  expect(pageLabel(132, 132)).toBe("page 132");
  expect(pageLabel(132, 133, true)).toBe("pp.132–133");
  expect(pageLabel(7, null, true)).toBe("p.7");
  expect(pageLabel(null)).toBe("");
  expect(pageLabel(undefined, 3)).toBe("");
});
