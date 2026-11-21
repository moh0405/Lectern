"use client";

import { useSyncExternalStore } from "react";

/** Reading theme (dark desk or light paper). The key is read by the inline script in app/layout.tsx; do not rename it. */
export const THEME_KEY = "lectern-reading-theme";
const CHANGE_EVENT = "lectern-theme-change";

export type Theme = "light" | "dark";

export function getTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* The theme still applies for this visit when storage is unavailable. */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function toggleTheme(): Theme {
  const next: Theme = getTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}

function subscribe(update: () => void) {
  const storage = (event: StorageEvent) => {
    if (event.key !== THEME_KEY && event.key !== null) return;
    document.documentElement.dataset.theme = event.newValue === "light" ? "light" : "dark";
    update();
  };
  window.addEventListener("storage", storage);
  window.addEventListener(CHANGE_EVENT, update);
  return () => {
    window.removeEventListener("storage", storage);
    window.removeEventListener(CHANGE_EVENT, update);
  };
}

/** The current theme; follows changes from this tab and others. */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, getTheme, () => "dark");
}
