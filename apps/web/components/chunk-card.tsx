import { ExternalLink } from "lucide-react";
import type { Chunk } from "@ai-study-mentor/api-client";
import { queryTerms, splitByTerms } from "@/lib/highlight";
import { cn } from "@/lib/utils";

export function scoreTone(score: number): "good" | "mid" | "low" {
  return score >= 0.6 ? "good" : score >= 0.35 ? "mid" : "low";
}

export function ChunkCard({ chunk, query, index }: { chunk: Chunk; query: string; index?: number }) {
  const tone = scoreTone(chunk.score);
  const text = chunk.text.length > 600 ? `${chunk.text.slice(0, 600)}…` : chunk.text;
  const href = chunk.citation_url ?? chunk.url ?? undefined;
  return (
    <article className="rounded-lg border border-border bg-bg/50 p-3 text-sm">
      <div className="mb-2 flex items-center justify-between gap-2 text-xs text-muted">
        <span className="min-w-0 truncate">
          {index !== undefined ? <span className="mr-1.5 font-mono text-fg">[{index + 1}]</span> : null}
          {chunk.doc}
          {chunk.page ? ` · page ${chunk.page}` : ""}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {href ? (
            <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-accent-2 hover:underline">
              open <ExternalLink className="h-3 w-3" />
            </a>
          ) : null}
          <span
            title="Relevance score"
            className={cn(
              "rounded-full px-2 py-0.5 font-mono font-semibold text-bg",
              tone === "good" && "bg-good",
              tone === "mid" && "bg-warn",
              tone === "low" && "bg-bad",
            )}
          >
            {chunk.score.toFixed(2)}
          </span>
        </span>
      </div>
      <p className="whitespace-pre-wrap leading-relaxed text-fg/90">
        {splitByTerms(text, queryTerms(query)).map((p, i) =>
          p.match ? (
            <mark key={i} className="hl">
              {p.text}
            </mark>
          ) : (
            <span key={i}>{p.text}</span>
          ),
        )}
      </p>
    </article>
  );
}
