/**
 * The header's API status light, as a small state machine kept free of React so it can be tested with fake timers.
 *
 * A Lambda cold start takes 10–45 s. During it the proxy answers 502/503/504 (or the request fails outright), and
 * the API itself answers `{status: "starting"}` while it loads. Neither means the service is gone, so the light says
 * "Starting up…" and re-checks quickly for COLD_START_WINDOW_MS before it says "Offline". It keeps checking after
 * that, more slowly, so it recovers on its own.
 */

/** What one health check said. `down`: no answer, a 5xx, or anything else that is not a usable health report. */
export type HealthOutcome = "ok" | "starting" | "down" | "busy";
export type ApiState = "checking" | "starting" | "online" | "busy" | "offline";

/** How long an unanswered or starting service is shown as "Starting up…" before "Offline". */
export const COLD_START_WINDOW_MS = 60_000;
/** Re-check delays while starting, one per consecutive failed check; the last one repeats. */
export const STARTING_BACKOFF_MS = [2_000, 2_000, 3_000, 3_000, 5_000, 5_000, 8_000, 10_000] as const;
/** Re-check delay once "Offline" is shown. */
export const OFFLINE_POLL_MS = 15_000;
/** Re-check delay while the service is rate limiting us. */
export const BUSY_POLL_MS = 15_000;
/** Re-check delay while healthy. */
export const HEALTHY_POLL_MS = 30_000;

/** The run of checks since the service was last healthy. */
export interface HealthStreak {
  /** The latest check's result. */
  outcome: HealthOutcome;
  /** When the current run of unhealthy checks began (null while healthy or busy). */
  since: number | null;
  /** Unhealthy checks in a row. */
  failures: number;
}

/** Classify a failed request: 429 is a real answer ("busy"); anything else means the service is not answering yet. */
export function outcomeOfError(error: unknown): HealthOutcome {
  const status = (error as { status?: unknown } | null)?.status;
  return status === 429 ? "busy" : "down";
}

/** Fold one check's result into the streak. */
export function recordHealth(prev: HealthStreak | undefined, outcome: HealthOutcome, now: number): HealthStreak {
  if (outcome === "ok" || outcome === "busy") return { outcome, since: null, failures: 0 };
  return { outcome, since: prev?.since ?? now, failures: (prev?.failures ?? 0) + 1 };
}

/** True once a service that is not answering has been unreachable for longer than a cold start can take. */
function pastWindow(streak: HealthStreak, now: number): boolean {
  return streak.since !== null && now - streak.since >= COLD_START_WINDOW_MS;
}

/**
 * What the light shows. An API that answers `starting` is alive and loading, so it stays "Starting up…" however
 * long that takes; only an unanswered service turns "Offline", and only after the cold-start window.
 */
export function apiStateOf(streak: HealthStreak | undefined, now: number): ApiState {
  if (!streak) return "checking";
  switch (streak.outcome) {
    case "ok": return "online";
    case "busy": return "busy";
    case "starting": return "starting";
    case "down": return pastWindow(streak, now) ? "offline" : "starting";
  }
}

/** How long to wait before the next check. */
export function nextCheckDelay(streak: HealthStreak | undefined, now: number): number {
  if (!streak) return STARTING_BACKOFF_MS[0];
  if (streak.outcome === "ok") return HEALTHY_POLL_MS;
  if (streak.outcome === "busy") return BUSY_POLL_MS;
  if (streak.outcome === "down" && pastWindow(streak, now)) return OFFLINE_POLL_MS;
  const i = Math.min(Math.max(streak.failures, 1), STARTING_BACKOFF_MS.length) - 1;
  return STARTING_BACKOFF_MS[i] ?? OFFLINE_POLL_MS;
}
