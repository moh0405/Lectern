import { expect, it } from "vitest";
import { plural } from "./format";

it("pluralizes and formats numbers", () => {
  expect(plural(0, "chunk")).toBe("0 chunks");
  expect(plural(1, "chunk")).toBe("1 chunk");
  expect(plural(1234, "chunk")).toBe("1,234 chunks");
  expect(plural(2, "match", "matches")).toBe("2 matches");
});
