"use client";

import { useSyncExternalStore } from "react";

/** Does this media query match? `serverValue` is used while rendering on the server and during hydration. */
export function useMediaQuery(query: string, serverValue: boolean): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : serverValue),
    () => serverValue,
  );
}

/** Tailwind's `lg` breakpoint: wide enough for the results and the problem side by side. */
export const useWideLayout = () => useMediaQuery("(min-width: 1024px)", true);
