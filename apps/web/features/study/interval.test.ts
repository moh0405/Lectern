import { describe, expect, it } from "vitest";
import { describeInterval, GRADES } from "./interval";

describe("describeInterval", () => {
  it("speaks in days, then months, then years", () => {
    expect(describeInterval(1)).toBe("tomorrow");
    expect(describeInterval(6)).toBe("in 6 days");
    expect(describeInterval(29)).toBe("in 29 days");
    expect(describeInterval(30)).toBe("in about 1 month");
    expect(describeInterval(75)).toBe("in about 3 months");
    expect(describeInterval(365)).toBe("in about 1 year");
    expect(describeInterval(730)).toBe("in about 2 years");
  });
});

describe("GRADES", () => {
  it("maps the buttons to increasing SM-2 grades, with only Again being a lapse", () => {
    expect(GRADES.map((g) => g.grade)).toEqual([1, 3, 4, 5]);
    expect(GRADES.filter((g) => g.grade < 3)).toHaveLength(1);
  });
});
