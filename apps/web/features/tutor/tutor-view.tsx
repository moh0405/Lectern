"use client";

import { useRef, type KeyboardEvent } from "react";
import { PageHeader } from "@/components/page-header";
import { useDemo } from "@/lib/demo";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { Adaptive } from "./adaptive";
import { ConceptMap } from "./concept-map";
import { Socratic } from "./socratic";
import { Synthesis } from "./synthesis";

const TOOLS = [
  { id: "map", label: "Concept map", blurb: "See how the ideas in a topic connect.", Component: ConceptMap },
  { id: "socratic", label: "Socratic tutor", blurb: "Work it out yourself, with guiding questions and hints.", Component: Socratic },
  { id: "synthesis", label: "Compare sources", blurb: "See where your documents agree and differ.", Component: Synthesis },
  { id: "adaptive", label: "Explain at my level", blurb: "The same answer, from ELI5 to expert.", Component: Adaptive },
] as const;

/** Index of the tab a key moves to (ARIA tabs pattern: arrows wrap, Home/End jump), or null. */
export function nextTabIndex(key: string, current: number, count: number): number | null {
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return (current + 1) % count;
    case "ArrowLeft":
    case "ArrowUp":
      return (current - 1 + count) % count;
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}

export function TutorView() {
  const url = useUrlParams();
  const demo = useDemo();
  const active = TOOLS.find((t) => t.id === url.get("tool")) ?? TOOLS[0];
  const activeIndex = TOOLS.indexOf(active);
  const Active = active.Component;
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);

  const select = (i: number) => url.set({ tool: i === 0 ? null : (TOOLS[i]?.id ?? null) });
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const next = nextTabIndex(e.key, activeIndex, TOOLS.length);
    if (next === null) return;
    e.preventDefault();
    select(next); // automatic activation: the panels are cheap to show (nothing runs until you submit)
    tabs.current[next]?.focus();
  };

  return (
    <>
      <PageHeader title="Tutor tools" description={active.blurb} />
      <div
        role="tablist"
        aria-label="Tutor tools"
        onKeyDown={onKeyDown}
        className="mb-5 grid grid-cols-2 gap-1 border-b border-border sm:flex sm:flex-wrap"
      >
        {TOOLS.map((t, i) => {
          const selected = i === activeIndex;
          return (
            <button
              key={t.id}
              ref={(el) => {
                tabs.current[i] = el;
              }}
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={selected}
              aria-controls="tool-panel"
              tabIndex={selected ? 0 : -1}
              type="button"
              onClick={() => select(i)}
              className={cn(
                "-mb-px min-h-11 border-b-2 px-3 py-2 text-left text-sm transition-colors sm:shrink-0 sm:px-4 sm:text-center",
                selected ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      {demo ? (
        <p className="-mt-2 mb-4 text-xs text-muted" data-testid="demo-scope">
          Uses the shared textbooks; your browser documents are used on Ask.
        </p>
      ) : null}
      <div role="tabpanel" id="tool-panel" aria-labelledby={`tab-${active.id}`}>
        <Active key={active.id} />
      </div>
    </>
  );
}
