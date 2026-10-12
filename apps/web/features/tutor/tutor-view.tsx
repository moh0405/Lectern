"use client";

import { PageHeader } from "@/components/page-header";
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

export function TutorView() {
  const url = useUrlParams();
  const active = TOOLS.find((t) => t.id === url.get("tool")) ?? TOOLS[0];
  const Active = active.Component;

  return (
    <>
      <PageHeader title="Tutor tools" description={active.blurb} />
      <div role="tablist" aria-label="Tutor tools" className="mb-5 flex gap-1 overflow-x-auto border-b border-border">
        {TOOLS.map((t) => {
          const selected = t.id === active.id;
          return (
            <button
              key={t.id}
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={selected}
              aria-controls="tool-panel"
              type="button"
              onClick={() => url.set({ tool: t.id === TOOLS[0].id ? null : t.id })}
              className={cn(
                "-mb-px shrink-0 border-b-2 px-4 py-2 text-sm transition-colors",
                selected ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" id="tool-panel" aria-labelledby={`tab-${active.id}`}>
        <Active />
      </div>
    </>
  );
}
