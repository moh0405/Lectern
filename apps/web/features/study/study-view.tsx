"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorNotice, Notice, Skeleton, Spinner } from "@/components/ui/feedback";
import { Input, Label, Textarea } from "@/components/ui/field";
import { QueryError } from "@/features/shared/query-error";
import { useDemo } from "@/lib/demo";
import { addLocalCard, deleteLocalCard, listLocalCards, reviewLocalCard } from "@/lib/local-cards";
import { toCsvRows } from "@/lib/csv";
import { ApiError, api, errorMessage, unwrap } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { plural } from "@/lib/format";
import { describeInterval, GRADES, nextIntervalDays, shortInterval } from "./interval";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value.toLocaleString()}</p>
    </Card>
  );
}

function Loading({ label, className }: { label: string; className?: string }) {
  return (
    <div role="status" className={className}>
      <Skeleton className="h-full min-h-16" />
      <p className="mt-2 text-sm text-muted">{label}</p>
    </div>
  );
}

const typing = (target: EventTarget) => target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

function Review({ onReviewed }: { onReviewed: () => void }) {
  const qc = useQueryClient();
  const [shown, setShown] = useState(false);
  const [last, setLast] = useState("");
  const [reviewed, setReviewed] = useState(0);
  // Where keyboard focus goes after the next render: the grade buttons after a reveal, the next question after a grade.
  const [moveFocus, setMoveFocus] = useState<"grades" | "question" | null>(null);
  const question = useRef<HTMLHeadingElement>(null);
  const firstGrade = useRef<HTMLButtonElement>(null);
  const doneHeading = useRef<HTMLHeadingElement>(null);
  const hintId = useId();
  const demo = useDemo();
  const due = useQuery({
    queryKey: ["cards", "due"],
    // In the public demo the deck lives in this browser.
    queryFn: async () => (demo ? listLocalCards({ dueOnly: true }) : unwrap(await api.http.GET("/api/v1/cards", { params: { query: { due: true, limit: 100 } } }))),
  });
  const review = useMutation({
    mutationFn: async ({ id, grade }: { id: number; grade: number }) =>
      demo ? reviewLocalCard(id, grade) : unwrap(await api.http.POST("/api/v1/cards/{card_id}/review", { params: { path: { card_id: id } }, body: { grade } })),
    onSuccess: async (card) => {
      setLast(`Saved. Next review ${describeInterval(card.interval_days)}.`);
      setReviewed((n) => n + 1);
      await qc.invalidateQueries({ queryKey: ["cards"] });
      setShown(false);
      setMoveFocus("question");
      onReviewed();
    },
  });

  useEffect(() => {
    if (!moveFocus) return;
    if (moveFocus === "grades") firstGrade.current?.focus();
    else (question.current ?? doneHeading.current)?.focus();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a one-shot focus request, cleared once handled
    setMoveFocus(null);
  }, [moveFocus, due.data]);

  const status = <p className="mb-2 min-h-5 text-sm text-muted" role="status">{last}</p>;
  if (due.isPending) return <Loading label="Loading cards due for review…" className="h-48" />;
  if (due.isError) return <QueryError error={due.error} what="the cards due for review" onRetry={() => void due.refetch()} retrying={due.isFetching} />;
  const card = due.data.cards[0];
  if (!card) {
    const empty = due.data.stats.total === 0;
    return (
      <>
        {status}
        <div className="rounded-xl border border-dashed border-border p-8 text-center">
          <h2 ref={doneHeading} tabIndex={-1} className="font-medium">{empty ? "No flashcards yet" : "All caught up"}</h2>
          <p className="mt-1 text-sm text-muted">
            {empty
              ? demo ? "Add your first card below. Your cards are saved in this browser." : "Add a card below, or let the model write some from your sources."
              : `Nothing is due${reviewed ? ` after ${plural(reviewed, "review")}` : ""}. Come back later, or add more cards.`}
          </p>
        </div>
      </>
    );
  }

  const grade = (value: number) => { if (!review.isPending) review.mutate({ id: card.id, grade: value }); };
  const reveal = () => { setShown(true); setMoveFocus("grades"); };
  // Shortcuts work while focus is inside the review card, so they never fire while typing elsewhere (WCAG 2.1.4).
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.altKey || event.ctrlKey || event.metaKey || typing(event.target)) return;
    if (!shown && event.key === " " && !(event.target instanceof HTMLButtonElement)) {
      event.preventDefault();
      reveal();
    } else if (shown) {
      const match = GRADES.find((g) => g.key === event.key);
      if (match) { event.preventDefault(); grade(match.grade); }
    }
  };

  return (
    <>
      {status}
      <Card className="space-y-4" aria-label="Review" onKeyDown={onKeyDown}>
        <div className="flex min-w-0 items-center justify-between gap-3 text-xs text-muted">
          <span className="shrink-0 tabular-nums">Card {reviewed + 1} of {reviewed + due.data.stats.due}</span>
          {card.source ? <span className="min-w-0 truncate" title={card.source}>{card.source}</span> : null}
        </div>
        <h2 ref={question} tabIndex={-1} aria-describedby={hintId} className="text-lg font-semibold leading-snug [overflow-wrap:anywhere]">{card.front}</h2>
        {shown ? (
          <>
            <p className="whitespace-pre-wrap rounded-lg border border-border bg-bg/40 p-4 text-sm [overflow-wrap:anywhere]" data-testid="card-back">
              {card.back}
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label="How well did you remember it?">
              {GRADES.map((g, index) => (
                <Button
                  key={g.label}
                  ref={index === 0 ? firstGrade : undefined}
                  variant={g.label === "Again" ? "danger" : "secondary"}
                  title={`${g.hint} (key ${g.key})`}
                  aria-keyshortcuts={g.key}
                  disabled={review.isPending}
                  className="h-auto flex-col gap-0 py-2"
                  onClick={() => grade(g.grade)}
                >
                  <span>{g.label}<span className="sr-only">, next review in</span></span>
                  <span className="text-xs font-normal">{shortInterval(nextIntervalDays(card, g.grade))}</span>
                </Button>
              ))}
            </div>
          </>
        ) : (
          <Button aria-keyshortcuts="Space" onClick={reveal}>Show answer</Button>
        )}
        <p id={hintId} className="text-xs text-muted">Keyboard: Space shows the answer, then 1 to 4 picks Again, Hard, Good or Easy.</p>
        {review.isError ? <ErrorNotice>{errorMessage(review.error)}</ErrorNotice> : null}
      </Card>
    </>
  );
}

export function StudyView() {
  const qc = useQueryClient();
  const demo = useDemo();
  const ids = useId();
  const deck = useQuery({
    queryKey: ["cards", "all"],
    queryFn: async () => (demo ? listLocalCards() : unwrap(await api.http.GET("/api/v1/cards", { params: { query: { limit: 1000 } } }))),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["cards"] });
  const [announcement, setAnnouncement] = useState("");

  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const [invalid, setInvalid] = useState<{ front?: boolean; back?: boolean }>({});
  const frontInput = useRef<HTMLInputElement>(null);
  const backInput = useRef<HTMLTextAreaElement>(null);
  const add = useMutation({
    mutationFn: async () => (demo ? addLocalCard(front, back) : unwrap(await api.http.POST("/api/v1/cards", { body: { front, back } }))),
    onSuccess: async () => {
      setFront("");
      setBack("");
      setAnnouncement("Card added to your deck.");
      await refresh();
      frontInput.current?.focus();
    },
  });
  const submitCard = () => {
    const missing = { front: !front.trim(), back: !back.trim() };
    setInvalid(missing);
    if (missing.front) frontInput.current?.focus();
    else if (missing.back) backInput.current?.focus();
    else if (!add.isPending) add.mutate();
  };

  const [topic, setTopic] = useState("");
  const generate = useMutation({
    mutationFn: async () => unwrap(await api.http.POST("/api/v1/cards/generate", { body: { topic: topic.trim() || undefined, n: 5 } })),
    onSuccess: () => void refresh(),
  });
  const generateCode = generate.error instanceof ApiError ? generate.error.code : null;

  const [confirm, setConfirm] = useState<number | null>(null);
  const [focusAfterDelete, setFocusAfterDelete] = useState<number | "front" | null>(null);
  const cards = deck.data?.cards ?? [];
  const remove = useMutation({
    mutationFn: async (id: number) => {
      if (demo) return deleteLocalCard(id);
      const res = await api.http.DELETE("/api/v1/cards/{card_id}", { params: { path: { card_id: id } } });
      if (res.error !== undefined) throw new Error("Could not delete the card");
    },
    onSuccess: async (_data, id) => {
      const index = cards.findIndex((c) => c.id === id);
      const next = cards[index + 1] ?? cards[index - 1];
      setAnnouncement(`Deleted card “${cards[index]?.front ?? ""}”.`);
      setConfirm(null);
      await refresh();
      setFocusAfterDelete(next ? next.id : "front");
    },
  });
  useEffect(() => { if (confirm !== null) document.getElementById(`${ids}-confirm`)?.focus(); }, [confirm, ids]);
  useEffect(() => {
    if (focusAfterDelete === null) return;
    const target = focusAfterDelete === "front" ? null : document.getElementById(`${ids}-delete-${focusAfterDelete}`);
    (target ?? document.getElementById(`${ids}-deck`) ?? frontInput.current)?.focus();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a one-shot focus request, cleared once handled
    setFocusAfterDelete(null);
  }, [focusAfterDelete, ids, deck.data]);
  const cancelDelete = (id: number) => {
    setConfirm(null);
    remove.reset();
    requestAnimationFrame(() => document.getElementById(`${ids}-delete-${id}`)?.focus());
  };

  const exportAs = useMutation({
    mutationFn: async (format: "csv" | "apkg") => {
      if (demo) {
        const rows = listLocalCards().cards.map((c) => [c.front, c.back]);
        downloadBlob(new Blob([toCsvRows(rows)], { type: "text/csv" }), "flashcards.csv");
        return;
      }
      const res = await api.http.GET("/api/v1/cards/export", { params: { query: { format } }, parseAs: "blob" });
      if (res.error !== undefined || !res.data) {
        const body = res.error as { error?: { message?: string } } | undefined;
        throw new Error(body?.error?.message ?? "Export failed");
      }
      downloadBlob(res.data as Blob, `flashcards.${format}`);
    },
  });

  const stats = deck.data?.stats;
  const fieldError = (show: boolean | undefined, id: string, text: string) => (show ? <p id={id} className="mt-1 text-sm text-bad">{text}</p> : null);
  return (
    <>
      <PageHeader
        title="Flashcards"
        description="Spaced repetition (SM-2, the scheduler behind Anki). Cards you remember come back less and less often; cards you forget come back tomorrow."
        actions={
          stats && stats.total > 0 ? (
            <div className="flex flex-wrap gap-1">
              <Button variant="ghost" size="sm" onClick={() => exportAs.mutate("csv")} disabled={exportAs.isPending}>
                <Download className="h-4 w-4" aria-hidden="true" /> CSV
              </Button>
              {demo ? null : (
                <Button variant="ghost" size="sm" onClick={() => exportAs.mutate("apkg")} disabled={exportAs.isPending}>
                  <Download className="h-4 w-4" aria-hidden="true" /> Anki
                </Button>
              )}
            </div>
          ) : undefined
        }
      />
      {exportAs.isError ? <ErrorNotice className="mb-3">{errorMessage(exportAs.error)}</ErrorNotice> : null}
      <p className="sr-only" role="status">{announcement}</p>

      {deck.isPending ? (
        <Loading label="Loading your flashcards…" className="mb-6 h-48" />
      ) : deck.isError ? (
        <QueryError className="mb-6" error={deck.error} what="your flashcards" onRetry={() => void qc.refetchQueries({ queryKey: ["cards"] })} retrying={deck.isFetching} />
      ) : (
        <>
          {stats && stats.total > 0 ? (
            <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Due now" value={stats.due} />
              <Stat label="New" value={stats.new_cards} />
              <Stat label="Mature (21+ days)" value={stats.mature} />
              <Stat label="Total" value={stats.total} />
            </div>
          ) : null}
          <section className="mb-6" aria-label="Review session">
            <Review onReviewed={() => void refresh()} />
          </section>
        </>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <CardTitle>Add a card</CardTitle>
          <form
            className="space-y-3"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              submitCard();
            }}
          >
            <div>
              <Label htmlFor="card-front">Front (question)</Label>
              <Input
                ref={frontInput}
                id="card-front"
                value={front}
                onChange={(e) => { setFront(e.target.value); if (invalid.front) setInvalid((v) => ({ ...v, front: false })); }}
                maxLength={1200}
                aria-invalid={invalid.front || undefined}
                aria-describedby={invalid.front ? `${ids}-front-error` : undefined}
              />
              {fieldError(invalid.front, `${ids}-front-error`, "Write the question for the front of the card.")}
            </div>
            <div>
              <Label htmlFor="card-back">Back (answer)</Label>
              <Textarea
                ref={backInput}
                id="card-back"
                rows={3}
                value={back}
                onChange={(e) => { setBack(e.target.value); if (invalid.back) setInvalid((v) => ({ ...v, back: false })); }}
                maxLength={1200}
                aria-invalid={invalid.back || undefined}
                aria-describedby={invalid.back ? `${ids}-back-error` : undefined}
              />
              {fieldError(invalid.back, `${ids}-back-error`, "Write the answer for the back of the card.")}
            </div>
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? <Spinner /> : <Plus className="h-4 w-4" aria-hidden="true" />} Add card
            </Button>
            {add.isError ? <ErrorNotice>{errorMessage(add.error)}</ErrorNotice> : null}
          </form>
        </Card>

        <Card className="space-y-3">
          <CardTitle>Write cards from your material</CardTitle>
          {demo ? (
            <p className="text-sm text-muted">
              In the public demo, cards are made by hand and saved in this browser only. Writing cards from your material
              uses the server&apos;s source index and model, which run on a private deployment of Lectern.
            </p>
          ) : (
            <>
              <p className="text-sm text-muted">The model reads passages from your sources and writes up to five cards. Review them below; delete any you do not like.</p>
              <div>
                <Label htmlFor="gen-topic">Topic (optional)</Label>
                <Input id="gen-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. hash tables" maxLength={200} />
              </div>
              <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
                {generate.isPending ? <Spinner /> : <Sparkles className="h-4 w-4" aria-hidden="true" />} Generate cards
              </Button>
              {generateCode === "llm_unavailable" ? (
                <Notice>The server has no language-model key configured, so it cannot write cards. You can still add them by hand.</Notice>
              ) : generateCode === "no_material" ? (
                <Notice>Add some sources first; cards are written from your indexed material.</Notice>
              ) : generate.isError ? (
                <ErrorNotice>{errorMessage(generate.error)}</ErrorNotice>
              ) : generate.isSuccess ? (
                <p className="text-sm text-muted" role="status">Added to your deck.</p>
              ) : null}
            </>
          )}
        </Card>
      </div>

      {cards.length ? (
        <section className="mt-6" aria-label="Deck">
          <h2 id={`${ids}-deck`} tabIndex={-1} className="mb-2 text-sm font-semibold text-muted">Deck ({cards.length})</h2>
          {remove.isError ? <ErrorNotice className="mb-2">{errorMessage(remove.error)}. The card was not deleted; try again or cancel.</ErrorNotice> : null}
          <ul className="space-y-2">
            {cards.map((c) => (
              <li key={c.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-border bg-surface/80 p-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium [overflow-wrap:anywhere]">{c.front}</p>
                  <p className="mt-0.5 line-clamp-2 text-sm text-muted [overflow-wrap:anywhere]">{c.back}</p>
                  <p className="mt-1 text-xs text-muted">
                    {c.reviews === 0 ? "New" : `Interval ${shortInterval(c.interval_days)}`}
                    {c.lapses ? ` · ${plural(c.lapses, "lapse")}` : ""}
                  </p>
                </div>
                {confirm === c.id ? (
                  <div
                    className="grid w-full gap-2 rounded-lg border border-bad/40 p-3 sm:w-auto sm:max-w-72"
                    role="group"
                    aria-label={`Delete card: ${c.front}?`}
                    onKeyDown={(event) => { if (event.key === "Escape" && !remove.isPending) cancelDelete(c.id); }}
                  >
                    <p className="text-xs">Delete this card and its review history?</p>
                    <div className="flex flex-wrap gap-2">
                      <Button id={`${ids}-confirm`} variant="danger" size="sm" disabled={remove.isPending} onClick={() => remove.mutate(c.id)}>
                        {remove.isPending ? "Deleting…" : "Confirm delete"}
                      </Button>
                      <Button variant="ghost" size="sm" disabled={remove.isPending} onClick={() => cancelDelete(c.id)}>Cancel</Button>
                    </div>
                  </div>
                ) : (
                  <Button id={`${ids}-delete-${c.id}`} variant="ghost" size="icon" aria-label={`Delete card: ${c.front}`} onClick={() => { remove.reset(); setConfirm(c.id); }}>
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
