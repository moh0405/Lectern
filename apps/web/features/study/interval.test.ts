import { describe, expect, it } from "vitest";
import { describeInterval, GRADES, nextIntervalDays, shortInterval } from "./interval";

describe("nextIntervalDays", () => {
  const fresh = { interval_days: 0, repetitions: 0, ef: 2.5 };
  const seasoned = { interval_days: 6, repetitions: 2, ef: 2.5 };
  it("follows SM-2: a lapse is tomorrow, then 1 day, 6 days, then interval times ease", () => {
    expect(nextIntervalDays(seasoned, 1)).toBe(1);
    expect(nextIntervalDays(fresh, 4)).toBe(1);
    expect(nextIntervalDays({ ...fresh, repetitions: 1, interval_days: 1 }, 4)).toBe(6);
    expect(nextIntervalDays(seasoned, 4)).toBe(15);
  });
  it("has a short form for the grade buttons", () => {
    expect(shortInterval(1)).toBe("1 day");
    expect(shortInterval(15)).toBe("15 days");
    expect(GRADES.map((g) => g.key)).toEqual(["1", "2", "3", "4"]);
  });
});

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
