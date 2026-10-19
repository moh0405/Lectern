"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Notice, Skeleton, Spinner } from "@/components/ui/feedback";
import { Input, Label, Textarea } from "@/components/ui/field";
import { useDemo, demoDisabled } from "@/lib/demo";
import { ApiError, api, errorMessage, unwrap } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { plural } from "@/lib/format";
import { describeInterval, GRADES } from "./interval";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value.toLocaleString()}</p>
    </Card>
  );
}

function Review({ onReviewed }: { onReviewed: () => void }) {
  const qc = useQueryClient();
  const [shown, setShown] = useState(false);
  const [last, setLast] = useState<string | null>(null);
  const demo = useDemo();
  const due = useQuery({
    queryKey: ["cards", "due"],
    queryFn: async () => (demo ? demoDisabled() : unwrap(await api.http.GET("/api/v1/cards", { params: { query: { due: true, limit: 100 } } }))),
  });
  const review = useMutation({
    mutationFn: async ({ id, grade }: { id: number; grade: number }) =>
      unwrap(await api.http.POST("/api/v1/cards/{card_id}/review", { params: { path: { card_id: id } }, body: { grade } })),
    onSuccess: (card) => {
      setShown(false);
      setLast(`Next review ${describeInterval(card.interval_days)}.`);
      void qc.invalidateQueries({ queryKey: ["cards"] });
      onReviewed();
    },
  });

  if (due.isPending) return <Skeleton className="h-48" />;
  if (due.isError) return <ErrorNotice>{errorMessage(due.error)}</ErrorNotice>;
  const card = due.data.cards[0];
  if (!card) {
    return (
      <EmptyState title={due.data.stats.total === 0 ? "No flashcards yet" : "All caught up"}>
        {last ? `${last} ` : null}
        {due.data.stats.total === 0 ? "Add a card below, or let the model write some from your material." : "Nothing is due. Come back later, or add more cards."}
      </EmptyState>
    );
  }
  return (
    <Card className="space-y-4" aria-label="Review">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{plural(due.data.stats.due, "card")} due</span>
        {card.source ? <span className="truncate">{card.source}</span> : null}
      </div>
      <p className="text-lg font-semibold leading-snug">{card.front}</p>
      {shown ? (
        <>
          <p className="whitespace-pre-wrap rounded-lg border border-border bg-bg/40 p-4 text-sm" data-testid="card-back">
            {card.back}
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label="How well did you remember it?">
            {GRADES.map((g) => (
              <Button
                key={g.label}
                variant={g.label === "Again" ? "danger" : "secondary"}
                title={g.hint}
                disabled={review.isPending}
                onClick={() => review.mutate({ id: card.id, grade: g.grade })}
              >
                {g.label}
              </Button>
            ))}
          </div>
        </>
      ) : (
        <Button onClick={() => setShown(true)}>Show answer</Button>
      )}
      {review.isError ? <ErrorNotice>{errorMessage(review.error)}</ErrorNotice> : null}
      {last ? <p className="text-xs text-muted">{last}</p> : null}
    </Card>
  );
}

export function StudyView() {
  const qc = useQueryClient();
  const demo = useDemo();
  const deck = useQuery({
    queryKey: ["cards", "all"],
    queryFn: async () => (demo ? demoDisabled() : unwrap(await api.http.GET("/api/v1/cards", { params: { query: { limit: 1000 } } }))),
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["cards"] });

  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const add = useMutation({
    mutationFn: async () => unwrap(await api.http.POST("/api/v1/cards", { body: { front, back } })),
    onSuccess: () => {
      setFront("");
      setBack("");
      refresh();
    },
  });

  const [topic, setTopic] = useState("");
  const generate = useMutation({
    mutationFn: async () => unwrap(await api.http.POST("/api/v1/cards/generate", { body: { topic: topic.trim() || undefined, n: 5 } })),
    onSuccess: refresh,
  });
  const generateCode = generate.error instanceof ApiError ? generate.error.code : null;

  const remove = useMutation({
    mutationFn: async (id: number) => {
      const res = await api.http.DELETE("/api/v1/cards/{card_id}", { params: { path: { card_id: id } } });
      if (res.error !== undefined) throw new Error("Could not delete the card");
    },
    onSuccess: refresh,
  });

  const exportAs = useMutation({
    mutationFn: async (format: "csv" | "apkg") => {
      const res = await api.http.GET("/api/v1/cards/export", { params: { query: { format } }, parseAs: "blob" });
      if (res.error !== undefined || !res.data) {
        const body = res.error as { error?: { message?: string } } | undefined;
        throw new Error(body?.error?.message ?? "Export failed");
      }
      downloadBlob(res.data as Blob, `flashcards.${format}`);
    },
  });

  const stats = deck.data?.stats;
  return (
    <>
      <PageHeader
        title="Flashcards"
        description="Spaced repetition (SM-2, the scheduler behind Anki). Cards you remember come back less and less often; cards you forget come back tomorrow."
        actions={
          stats && stats.total > 0 ? (
            <div className="flex flex-wrap gap-1">
              <Button variant="ghost" size="sm" onClick={() => exportAs.mutate("csv")} disabled={exportAs.isPending}>
                <Download className="h-4 w-4" /> CSV
              </Button>
              <Button variant="ghost" size="sm" onClick={() => exportAs.mutate("apkg")} disabled={exportAs.isPending}>
                <Download className="h-4 w-4" /> Anki
              </Button>
            </div>
          ) : undefined
        }
      />
      {exportAs.isError ? <ErrorNotice className="mb-3">{errorMessage(exportAs.error)}</ErrorNotice> : null}

      {stats ? (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Due now" value={stats.due} />
          <Stat label="New" value={stats.new_cards} />
          <Stat label="Mature (21+ days)" value={stats.mature} />
          <Stat label="Total" value={stats.total} />
        </div>
      ) : null}

      <section className="mb-6" aria-label="Review session">
        <Review onReviewed={refresh} />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <CardTitle>Add a card</CardTitle>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (front.trim() && back.trim()) add.mutate();
            }}
          >
            <div>
              <Label htmlFor="card-front">Front (question)</Label>
              <Input id="card-front" value={front} onChange={(e) => setFront(e.target.value)} maxLength={1200} />
            </div>
            <div>
              <Label htmlFor="card-back">Back (answer)</Label>
              <Textarea id="card-back" rows={3} value={back} onChange={(e) => setBack(e.target.value)} maxLength={1200} />
            </div>
            <Button type="submit" disabled={add.isPending || !front.trim() || !back.trim()}>
              {add.isPending ? <Spinner /> : <Plus className="h-4 w-4" />} Add card
            </Button>
            {add.isError ? <ErrorNotice>{errorMessage(add.error)}</ErrorNotice> : null}
          </form>
        </Card>

        <Card className="space-y-3">
          <CardTitle>Write cards from your material</CardTitle>
          <p className="text-sm text-muted">The model reads passages from your sources and writes up to five cards. Review them below; delete any you do not like.</p>
          <div>
            <Label htmlFor="gen-topic">Topic (optional)</Label>
            <Input id="gen-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. hash tables" maxLength={200} />
          </div>
          <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
            {generate.isPending ? <Spinner /> : <Sparkles className="h-4 w-4" />} Generate cards
          </Button>
          {generateCode === "llm_unavailable" ? (
            <Notice>The server has no language-model key configured, so it cannot write cards. You can still add them by hand.</Notice>
          ) : generateCode === "no_material" ? (
            <Notice>Add some sources first; cards are written from your indexed material.</Notice>
          ) : generate.isError ? (
            <ErrorNotice>{errorMessage(generate.error)}</ErrorNotice>
          ) : generate.isSuccess ? (
            <p className="text-sm text-muted">Added to your deck.</p>
          ) : null}
        </Card>
      </div>

      <section className="mt-6" aria-label="Deck">
        <h2 className="mb-2 text-sm font-semibold text-muted">Deck{stats ? ` (${stats.total})` : ""}</h2>
        {deck.isError ? <ErrorNotice>{errorMessage(deck.error)}</ErrorNotice> : null}
        {remove.isError ? <ErrorNotice className="mb-2">{errorMessage(remove.error)}</ErrorNotice> : null}
        <ul className="space-y-2">
          {(deck.data?.cards ?? []).map((c) => (
            <li key={c.id} className="flex items-start justify-between gap-3 rounded-xl border border-border bg-surface/80 p-3">
              <div className="min-w-0">
                <p className="text-sm font-medium">{c.front}</p>
                <p className="mt-0.5 line-clamp-2 text-xs text-muted">{c.back}</p>
                <p className="mt-1 text-xs text-muted">
                  {c.reviews === 0 ? "new" : `interval ${c.interval_days}d · ease ${c.ef.toFixed(2)}`}
                  {c.lapses ? ` · ${plural(c.lapses, "lapse")}` : ""}
                </p>
              </div>
              <Button variant="ghost" size="icon" aria-label={`Delete card: ${c.front}`} onClick={() => remove.mutate(c.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
