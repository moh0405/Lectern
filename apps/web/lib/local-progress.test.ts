// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { loadLocalProgress, saveLocalProgress } from "./local-progress";

const two = { pid: "1", title: "Two Sum", difficulty: "Easy", topics: ["Array"] };

describe("local progress", () => {
  beforeEach(() => localStorage.clear());

  it("starts empty", () => {
    expect(loadLocalProgress().summary).toEqual({ solved: 0, attempted: 0, todo: 0, solved_by_difficulty: {} });
  });

  it("stores status, counts attempts and solved by difficulty", () => {
    saveLocalProgress(two, { status: "attempted" });
    saveLocalProgress(two, { status: "solved" }, 5);
    const { items, summary } = loadLocalProgress();
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ status: "solved", attempts: 2, solved_at: 5 });
    expect(summary).toMatchObject({ solved: 1, attempted: 0, solved_by_difficulty: { Easy: 1 } });
  });

  it("keeps notes when only the status changes", () => {
    saveLocalProgress(two, { status: "attempted", notes: "use a hash map" });
    saveLocalProgress(two, { status: "solved" });
    expect(loadLocalProgress().items[0]?.notes).toBe("use a hash map");
  });

  it("ignores corrupt storage", () => {
    localStorage.setItem("ai-study-mentor:lc-progress:v1", "{not json");
    expect(loadLocalProgress().items).toEqual([]);
  });
});
