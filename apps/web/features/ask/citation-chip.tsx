"use client";

import { AlertTriangle, ArrowUpRight, Check } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { Markdown } from "@/components/markdown";
import { CITE_PREFIX, twoDigits, type CiteRef, type LinkedAnswer } from "./citations";

/** What the source margin is showing: a citation chip (ref) and/or a retrieved passage (chunk). */
export interface Selection {
  ref: number | null;
  chunk: number | null;
  /** Text the passage should be highlighted against when no citation is selected (a step of a Try first attempt). */
  sentence?: string;
}

export const CITE_PROBLEM: Record<string, string> = {
  unknown_source: "that source was not among the passages it was given",
  page_not_retrieved: "that page was not among the passages it was given",
};

/**
 * Which citation is open, and how to open another. Chips read it from context, so selecting a citation re-renders
 * only the chips and never rebuilds the Markdown around them (a rebuilt chip would drop keyboard focus).
 */
interface CiteState {
  selectedRef: number | null;
  onSelect?: (selection: Selection) => void;
}
const CiteContext = createContext<CiteState>({ selectedRef: null });

export function CiteProvider({ selectedRef, onSelect, children }: CiteState & { children: ReactNode }) {
  const value = useMemo(() => ({ selectedRef, onSelect }), [selectedRef, onSelect]);
  return <CiteContext.Provider value={value}>{children}</CiteContext.Provider>;
}

/** A short visible name for a citation that has no passage: the document without its extension, and its page. */
export function shortCiteLabel(ref: Pick<CiteRef, "doc" | "page" | "label">, max = 18): string {
  const doc = (ref.doc || ref.label).replace(/\.[a-z0-9]{1,5}$/i, "").trim();
  const name = doc.length > max ? `${doc.slice(0, max - 1).trimEnd()}…` : doc;
  return ref.page != null ? `${name} p.${ref.page}` : name;
}

export function citationLabel(ref: CiteRef): string {
  if (ref.chunk !== null) return `Citation ${ref.label}: show passage ${ref.chunk + 1}`;
  if (ref.status === "ok") return `Verified citation ${ref.label}: its passage is not in the list of retrieved passages`;
  return `Unverified citation ${ref.label}: ${CITE_PROBLEM[ref.status] ?? "it could not be matched to a passage"}`;
}

/** A checked citation in an answer. Accessible names start with "Citation ", "Verified citation " or "Unverified citation ". */
export function CitationChip({ refInfo }: { refInfo: CiteRef }) {
  const { selectedRef, onSelect } = useContext(CiteContext);
  const active = selectedRef === refInfo.id;
  const linked = refInfo.chunk !== null;
  // The server verified it, but its passage is not among the ones listed for this answer.
  const unlisted = !linked && refInfo.status === "ok";
  return (
    <button
      type="button"
      id={`cite-chip-${refInfo.id}`}
      className={linked ? "cite-chip" : unlisted ? "cite-chip unlisted" : "cite-chip unverified"}
      aria-pressed={active}
      aria-label={citationLabel(refInfo)}
      title={refInfo.label}
      data-cite-active={active ? "true" : undefined}
      data-cite-id={refInfo.id}
      onClick={() => onSelect?.({ ref: refInfo.id, chunk: refInfo.chunk })}
    >
      {linked ? (
        <>
          {twoDigits(refInfo.chunk! + 1)}
          <ArrowUpRight aria-hidden="true" />
        </>
      ) : unlisted ? (
        <>
          <Check aria-hidden="true" />
          not listed
        </>
      ) : (
        <>
          <AlertTriangle aria-hidden="true" />
          <span className="cite-chip-label">{shortCiteLabel(refInfo)}</span>
        </>
      )}
    </button>
  );
}

/**
 * An answer whose checked citations render as chips. Memoised on the linked Markdown, so a change of selection
 * (read by the chips from `CiteProvider`) never remounts the answer. Reusable wherever citations are linked.
 */
export function CitedMarkdown({ markdown, linked, streaming }: { markdown: string; linked: LinkedAnswer | null; streaming?: boolean }) {
  const renderLink = useCallback(
    (href: string) => {
      if (!linked || !href.startsWith(CITE_PREFIX)) return undefined;
      const ref = linked.refs[Number(href.slice(CITE_PREFIX.length))];
      return ref ? <CitationChip refInfo={ref} /> : undefined;
    },
    [linked],
  );
  const hasRefs = Boolean(linked?.refs.length);
  return useMemo(
    () => (
      <Markdown streaming={streaming} renderLink={hasRefs ? renderLink : undefined}>
        {linked?.markdown ?? markdown}
      </Markdown>
    ),
    [streaming, hasRefs, renderLink, linked, markdown],
  );
}
