import { describe, expect, it } from "vitest";
import {
  apiStateOf, BUSY_POLL_MS, COLD_START_WINDOW_MS, HEALTHY_POLL_MS, nextCheckDelay, OFFLINE_POLL_MS, outcomeOfError, recordHealth,
  STARTING_BACKOFF_MS, type HealthOutcome, type HealthStreak,
} from "./api-status";

/** Run checks with the given outcomes, each one at the time the schedule asks for; return what the light showed. */
function simulate(outcomeAt: (t: number) => HealthOutcome, until: number) {
  let t = 0;
  let streak: HealthStreak | undefined;
  const log: { t: number; state: string; delay: number }[] = [];
  while (t <= until) {
    streak = recordHealth(streak, outcomeAt(t), t);
    const delay = nextCheckDelay(streak, t);
    log.push({ t, state: apiStateOf(streak, t), delay });
    t += delay;
  }
  return log;
}

describe("api status", () => {
  it("classifies failures: 429 is busy, anything else is not answering yet", () => {
    expect(outcomeOfError({ status: 429 })).toBe("busy");
    expect(outcomeOfError({ status: 503 })).toBe("down");
    expect(outcomeOfError({ status: 404 })).toBe("down");
    expect(outcomeOfError(new TypeError("Failed to fetch"))).toBe("down");
    expect(outcomeOfError(null)).toBe("down");
  });

  it("shows Connecting before the first answer", () => {
    expect(apiStateOf(undefined, 0)).toBe("checking");
    expect(nextCheckDelay(undefined, 0)).toBe(STARTING_BACKOFF_MS[0]);
  });

  it("re-checks quickly with backoff while starting, capped at 10 s", () => {
    const log = simulate(() => "down", 50_000);
    expect(log.map((l) => l.delay).slice(0, STARTING_BACKOFF_MS.length)).toEqual([...STARTING_BACKOFF_MS]);
    expect(Math.max(...log.map((l) => l.delay))).toBeLessThanOrEqual(10_000);
    expect(log.every((l) => l.state === "starting")).toBe(true);
  });

  it("says Starting up through a whole cold start and never Offline", () => {
    const log = simulate((t) => (t < 45_000 ? "down" : "ok"), 60_000);
    expect(log.some((l) => l.state === "offline")).toBe(false);
    const back = log.find((l) => l.state === "online")!;
    expect(back.t - 45_000).toBeLessThanOrEqual(10_000); // the next check finds it
    expect(back.delay).toBe(HEALTHY_POLL_MS);
  });

  it("finds an API that recovers after 8 s within about 2 s", () => {
    const log = simulate((t) => (t < 8_000 ? "down" : "ok"), 20_000);
    expect(log.find((l) => l.state === "online")!.t).toBeLessThanOrEqual(10_000);
  });

  it("turns Offline only after the cold-start window, then keeps checking more slowly and recovers", () => {
    const log = simulate((t) => (t < 120_000 ? "down" : "ok"), 160_000);
    const firstOffline = log.find((l) => l.state === "offline")!;
    expect(firstOffline.t).toBeGreaterThanOrEqual(COLD_START_WINDOW_MS);
    expect(log.filter((l) => l.t < COLD_START_WINDOW_MS).every((l) => l.state === "starting")).toBe(true);
    expect(firstOffline.delay).toBe(OFFLINE_POLL_MS);
    const back = log.find((l) => l.state === "online")!;
    expect(back.t).toBeLessThanOrEqual(120_000 + OFFLINE_POLL_MS);
    expect(back.delay).toBe(HEALTHY_POLL_MS);
  });

  it("keeps an API that answers 'starting' as Starting up, however long it takes", () => {
    const log = simulate(() => "starting", 120_000);
    expect(log.every((l) => l.state === "starting")).toBe(true);
    expect(log.at(-1)!.delay).toBe(10_000);
  });

  it("restarts the window after a healthy check", () => {
    let s = recordHealth(undefined, "down", 0);
    s = recordHealth(s, "down", 50_000);
    s = recordHealth(s, "ok", 55_000);
    expect(s).toEqual({ outcome: "ok", since: null, failures: 0 });
    s = recordHealth(s, "down", 70_000);
    expect(apiStateOf(s, 70_000)).toBe("starting");
    expect(nextCheckDelay(s, 70_000)).toBe(STARTING_BACKOFF_MS[0]);
  });

  it("polls a busy service at its own pace", () => {
    const s = recordHealth(recordHealth(undefined, "down", 0), "busy", 1_000);
    expect(apiStateOf(s, 1_000)).toBe("busy");
    expect(nextCheckDelay(s, 1_000)).toBe(BUSY_POLL_MS);
  });
});
