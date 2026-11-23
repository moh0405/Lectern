"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardTitle } from "@/components/ui/card";
import { loadTurns } from "@/features/ask/session";
import { similarHistory, type SimilarEntry } from "./similar-history";

/**
 * Practice questions from Ask's Understanding step, read from what this browser already saved. Opening one only fills
 * in the Ask composer, so nothing here calls a model.
 */
export function SimilarHistoryPanel() {
  const [entries, setEntries] = useState<SimilarEntry[]>([]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- browser storage is read once, after hydration
    setEntries(similarHistory(loadTurns()));
  }, []);
  return (
    <Card className="mt-6 space-y-3" data-testid="similar-history">
      <CardTitle>Similar examples</CardTitle>
      {entries.length ? (
        <ul className="divide-y divide-border">
          {entries.map((entry) => (
            <li key={entry.question} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium [overflow-wrap:anywhere]">{entry.question}</p>
                <p className="mt-0.5 text-xs text-muted [overflow-wrap:anywhere]">From “{entry.from}”{entry.source ? ` · ${entry.source}` : ""}</p>
              </div>
              <Link
                href={`/ask?q=${encodeURIComponent(entry.question)}`}
                aria-label={`Practise on Ask: ${entry.question}`}
                className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-3 text-sm text-accent-2 underline underline-offset-4"
              >
                Practise on Ask <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">No practice questions yet. After an answer on Ask, open Similar example to write one.</p>
      )}
    </Card>
  );
}
