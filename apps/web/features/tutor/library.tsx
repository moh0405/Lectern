"use client";

import { useQuery } from "@tanstack/react-query";
import { Library } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { api, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";

/** A suggestion chip; 44px tall on touch screens. */
export const chipClass =
  "inline-flex min-h-8 items-center rounded-full border border-border bg-surface-2 px-3 py-1 text-left text-xs text-muted transition-colors hover:border-accent hover:text-fg disabled:opacity-50 pointer-coarse:min-h-11";

/** The shared index's document names (same query key as Ask and Sources, so it is fetched once). */
export function useLibrary() {
  const q = useQuery({ queryKey: ["documents"], queryFn: async () => unwrap(await api.http.GET("/api/v1/documents")), staleTime: 60_000 });
  const names = [...new Set((q.data?.documents ?? []).flatMap((d) => (d.docs.length ? d.docs : [d.source_key])))];
  return { names, isPending: q.isPending, isError: q.isError };
}

/** "graph_algorithms-notes.pdf" → "Graph algorithms notes"; up to `max` distinct topics from file names. */
export function topicSuggestions(names: string[], max = 3): string[] {
  const out: string[] = [];
  for (const n of names) {
    const base = n.replace(/^https?:\/\/(www\.)?/, "").replace(/[?#].*$/, "").split("/").filter(Boolean).pop() ?? n;
    const words = base.replace(/\.[a-z0-9]{1,5}$/i, "").replace(/[_\-.+]+/g, " ").replace(/\s+/g, " ").trim();
    if (words.length < 3 || /^\d+$/.test(words)) continue;
    const topic = words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
    if (!out.includes(topic)) out.push(topic);
    if (out.length >= max) break;
  }
  return out;
}

const listNames = (names: string[]) => (names.length > 4 ? `${names.slice(0, 4).join(", ")} and ${names.length - 4} more` : names.join(", "));

/**
 * The idle state of a tool: what the result will contain, which material it reads, and topics to try.
 * `onPick` fills the tool's input (it never runs the tool: that costs a model call).
 */
export function IdlePreview({ items, onPick, pickLabel = "Try a topic from your library" }: { items: ReactNode[]; onPick?: (topic: string) => void; pickLabel?: string }) {
  const demo = useDemo();
  const lib = useLibrary();
  const topics = topicSuggestions(lib.names);
  return (
    <section className="rounded-xl border border-dashed border-border p-4 text-sm" aria-label="What you'll get" data-testid="idle-preview">
      <h2 className="eyebrow mb-2">What you&apos;ll get</h2>
      <ul className="list-disc space-y-1 pl-5 text-muted">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
      <LibraryLine names={lib.names} pending={lib.isPending} demo={demo} />
      {onPick && topics.length ? (
        <div className="mt-3">
          <p className="mb-1.5 text-xs text-muted">{pickLabel}</p>
          <div className="flex flex-wrap gap-2">
            {topics.map((t) => (
              <button key={t} type="button" onClick={() => onPick(t)} className={chipClass}>
                {t}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function LibraryLine({ names, pending, demo }: { names: string[]; pending: boolean; demo: boolean }) {
  if (pending) return null;
  return (
    <p className="mt-3 flex items-start gap-2 text-xs text-muted" data-testid="library-line">
      <Library className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-2" aria-hidden />
      <span>
        {names.length ? (
          <>
            {demo ? "Uses the shared textbooks: " : "Uses your library: "}
            <span className="font-mono">{listNames(names)}</span>.
          </>
        ) : (
          <>
            Nothing is indexed yet.{" "}
            <Link href="/sources" className="text-accent-2 underline">
              Add sources
            </Link>{" "}
            first.
          </>
        )}
      </span>
    </p>
  );
}
