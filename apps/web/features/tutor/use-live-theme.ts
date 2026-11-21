"use client";

import { useSyncExternalStore } from "react";

// The reading theme lives on <html data-theme>. The shell's theme button dispatches
// `lectern-theme-change`; another tab changes it through `storage`. Kept local (not imported from the
// shell) so tools pages only depend on the attribute.
function subscribe(update: () => void) {
  window.addEventListener("lectern-theme-change", update);
  window.addEventListener("storage", update);
  const observer = new MutationObserver(update);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => {
    window.removeEventListener("lectern-theme-change", update);
    window.removeEventListener("storage", update);
    observer.disconnect();
  };
}

const read = (): "light" | "dark" => (document.documentElement.dataset.theme === "light" ? "light" : "dark");

/** The live reading theme ("dark" while rendering on the server). */
export function useLiveTheme(): "light" | "dark" {
  return useSyncExternalStore(subscribe, read, () => "dark");
}
