// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { addLocalCard, deleteLocalCard, listLocalCards, reviewLocalCard } from "./local-cards";

describe("local flashcards", () => {
  beforeEach(() => localStorage.clear());

  it("adds a card that is due and new, and removes it", () => {
    const c = addLocalCard(" What is a hash? ", "A function", 100);
    expect(c.front).toBe("What is a hash?");
    expect(listLocalCards({ at: 100 }).stats).toEqual({ total: 1, due: 1, new_cards: 1, mature: 0, reviews: 0 });
    deleteLocalCard(c.id);
    expect(listLocalCards().stats.total).toBe(0);
  });

  it("follows SM-2: 1 day, then 6, then interval x EF; a lapse resets to 1 day", () => {
    const { id } = addLocalCard("q", "a", 0);
    expect(reviewLocalCard(id, 4, 0)).toMatchObject({ interval_days: 1, repetitions: 1, ef: 2.5 });
    expect(reviewLocalCard(id, 4, 0).interval_days).toBe(6);
    expect(reviewLocalCard(id, 4, 0).interval_days).toBe(15); // round(6 * 2.5)
    const lapsed = reviewLocalCard(id, 1, 0);
    expect(lapsed).toMatchObject({ interval_days: 1, repetitions: 0, lapses: 1 });
    expect(lapsed.ef).toBeGreaterThanOrEqual(1.3);
  });

  it("a reviewed card leaves the due queue until it is due again", () => {
    const { id } = addLocalCard("q", "a", 0);
    reviewLocalCard(id, 4, 0);
    expect(listLocalCards({ dueOnly: true, at: 10 }).cards).toHaveLength(0);
    expect(listLocalCards({ dueOnly: true, at: 86401 }).cards).toHaveLength(1);
  });

  it("ignores corrupt storage", () => {
    localStorage.setItem("ai-study-mentor:cards:v1", "nope");
    expect(listLocalCards().cards).toEqual([]);
  });
});
