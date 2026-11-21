"use client";

import { useSyncExternalStore } from "react";

/** The desk stacks its columns below this width (keep in step with ask.module.css). */
export const NARROW_QUERY = "(max-width: 1179px)";

/** Whether a media query matches; false on the server and where matchMedia is missing. */
export function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const list = window.matchMedia(query);
      list.addEventListener?.("change", notify);
      return () => list.removeEventListener?.("change", notify);
    },
    () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : false),
    () => false,
  );
}

export const prefersReducedMotion = () => typeof window !== "undefined" && Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
