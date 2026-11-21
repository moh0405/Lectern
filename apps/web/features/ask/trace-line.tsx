"use client";

import { useEffect, useState } from "react";
import styles from "./ask.module.css";

/** Only on wide screens, where the answer and the source margin sit side by side. */
const MIN_WIDTH = 1180;

interface Path {
  d: string;
  from: [number, number];
  to: [number, number];
}

function visibleIn(el: Element, box: DOMRect) {
  const scroller = el.closest("[data-desk-scroll]");
  if (!scroller) return true;
  const area = scroller.getBoundingClientRect();
  return box.top >= area.top - 2 && box.bottom <= area.bottom + 2;
}

function measure(): Path | null {
  if (window.innerWidth < MIN_WIDTH) return null;
  const chip = document.querySelector('[data-cite-active="true"]');
  const anchor = document.querySelector('[data-margin-anchor="true"]');
  if (!chip || !anchor) return null;
  const a = chip.getBoundingClientRect();
  const b = anchor.getBoundingClientRect();
  if (!visibleIn(chip, a) || !visibleIn(anchor, b) || b.left <= a.right) return null;
  const from: [number, number] = [a.right + 4, a.top + a.height / 2];
  const to: [number, number] = [b.left - 6, b.top + Math.min(b.height / 2, 14)];
  const bend = Math.max(40, (to[0] - from[0]) / 2);
  return { d: `M ${from[0]} ${from[1]} C ${from[0] + bend} ${from[1]}, ${to[0] - bend} ${to[1]}, ${to[0]} ${to[1]}`, from, to };
}

/**
 * A dotted line from the selected citation chip to its highlighted passage in the source margin.
 * Purely decorative (hidden from assistive technology); it follows scrolling, resizing and layout changes.
 */
export function TraceLine({ enabled, version }: { enabled: boolean; version: string }) {
  const [path, setPath] = useState<Path | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setPath(measure()));
    };
    update();
    // Layout settles after fonts load and the margin re-renders; check again shortly after.
    const late = window.setTimeout(update, 250);
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    // Layout also moves without a scroll or resize, for example when the margin expands a passage's context:
    // watch the answer column and the source margin (and what they hold) for size changes and new content.
    const margin = document.querySelector('aside[aria-label="Source margin"]');
    const watched = [document.querySelector("[data-desk-scroll]"), margin].filter((el): el is Element => el !== null);
    const resized = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    for (const el of watched) {
      resized?.observe(el);
      for (const child of Array.from(el.children)) resized?.observe(child);
    }
    const mutated = typeof MutationObserver === "undefined" || !margin ? null : new MutationObserver(update);
    if (margin) mutated?.observe(margin, { childList: true, subtree: true, characterData: true });
    return () => {
      resized?.disconnect();
      mutated?.disconnect();
      cancelAnimationFrame(frame);
      window.clearTimeout(late);
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [enabled, version]);
  if (!enabled || !path) return null;
  return (
    <svg className={styles.trace} aria-hidden="true" focusable="false">
      <path key={version} d={path.d} />
      <circle cx={path.from[0]} cy={path.from[1]} r="3" />
      <circle cx={path.to[0]} cy={path.to[1]} r="4" className={styles.traceEnd} />
    </svg>
  );
}
