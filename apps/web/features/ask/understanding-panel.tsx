"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Layers, NotebookPen, PenLine, RefreshCw, Shuffle } from "lucide-react";
import { useId, useState } from "react";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Label, Select, Textarea } from "@/components/ui/field";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";
import { pageLabel } from "@/lib/format";
import { addLocalCard } from "@/lib/local-cards";
import type { Explanation, SimilarExample, Turn } from "./session";
import { EXPLAIN_LEVELS, keyDistinction, MAX_CARD_FRONT, MAX_NOTE, toPassages, type EliLevel } from "./understanding";
import styles from "./ask.module.css";

type NoteSaved = "server" | "browser";

/** The learner's note, and a flashcard made from it. Nothing is saved until they ask. */
function OwnWords({ turn, onSaveNote, announce }: { turn: Turn; onSaveNote: (turn: Turn, note: string) => Promise<NoteSaved>; announce: (m: string) => void }) {
  const demo = useDemo();
  const qc = useQueryClient();
  const id = useId();
  const [draft, setDraft] = useState(() => turn.note ?? keyDistinction(turn.answer));
  const [savedNote, setSavedNote] = useState<{ text: string; where: NoteSaved } | null>(turn.note ? { text: turn.note, where: demo ? "browser" : "server" } : null);
  const [cardBack, setCardBack] = useState<string | null>(null);
  const text = draft.trim();
  const noteSaved = savedNote?.text === text && Boolean(text);
  const cardSaved = cardBack === text && Boolean(text);

  const persist = async () => {
    if (noteSaved) return savedNote!.where;
    const where = await onSaveNote(turn, text);
    setSavedNote({ text, where });
    return where;
  };
  const note = useMutation({
    mutationFn: persist,
    onSuccess: (where) => announce(where === "server" ? "Note saved to your history" : "Note saved in this browser"),
  });
  const card = useMutation({
    mutationFn: async () => {
      await persist();
      const front = turn.question.slice(0, MAX_CARD_FRONT);
      if (demo) addLocalCard(front, text);
      else unwrap(await api.http.POST("/api/v1/cards", { body: { front, back: text, source: turn.chunks[0]?.doc ?? null } }));
      return text;
    },
    onSuccess: (back) => {
      setCardBack(back);
      void qc.invalidateQueries({ queryKey: ["cards"] });
      announce(demo ? "Flashcard saved in this browser" : "Flashcard saved");
    },
    onError: (err) => announce(`Could not save the flashcard: ${errorMessage(err)}`),
  });
  const noteBlocked = !text || noteSaved || note.isPending;
  const cardBlocked = !text || cardSaved || card.isPending;

  return (
    <div className={styles.toolBody}>
      <Label htmlFor={`${id}-note`}>Your note</Label>
      <p id={`${id}-hint`} className={styles.toolHint}>{turn.note ? "Your saved note." : "This starts from the answer's key distinction. Rewrite it so it sounds like you."}</p>
      <Textarea id={`${id}-note`} aria-describedby={`${id}-hint`} value={draft} maxLength={MAX_NOTE} rows={3} className={styles.noteInput} onChange={(e) => setDraft(e.target.value)} />
      <div className={styles.toolActions}>
        <Button variant="secondary" size="sm" aria-disabled={noteBlocked || undefined} onClick={() => { if (!noteBlocked) note.mutate(); }}>
          {noteSaved ? <Check className="h-4 w-4 text-good" aria-hidden="true" /> : <NotebookPen className="h-4 w-4" aria-hidden="true" />}
          {noteSaved ? "Note saved" : "Save note"}
        </Button>
        <Button variant="ghost" size="sm" aria-disabled={cardBlocked || undefined} onClick={() => { if (!cardBlocked) card.mutate(); }}>
          {cardSaved ? <Check className="h-4 w-4 text-good" aria-hidden="true" /> : <Layers className="h-4 w-4" aria-hidden="true" />}
          {cardSaved ? "Flashcard saved" : "Save note as flashcard"}
        </Button>
        {noteSaved ? <span className={styles.toolHint}>{savedNote!.where === "server" ? "In your history." : "In this browser."}</span> : null}
      </div>
      {card.isError ? <ErrorNotice>Could not save the flashcard: {errorMessage(card.error)}</ErrorNotice> : null}
    </div>
  );
}

/** One new question on the same idea, fetched only on click. Its answer never reaches the browser. */
function Similar({ turn, busy, onSimilar, onPractise, announce }: { turn: Turn; busy: boolean; onSimilar: (turn: Turn, example: SimilarExample) => void; onPractise: (turn: Turn, question: string) => void; announce: (m: string) => void }) {
  const examples = turn.similar ?? [];
  const current = examples[examples.length - 1];
  const write = useMutation({
    mutationFn: async () =>
      unwrap(await api.http.POST("/api/v1/practice/similar", { body: { question: turn.question, context: toPassages(turn.chunks), previous: examples.slice(-5).map((e) => e.question) } })),
    onSuccess: (res) => {
      onSimilar(turn, { question: res.question, citations: res.citations });
      announce("Practice question ready. Its answer stays hidden.");
    },
    onError: (err) => announce(`Could not write a practice question: ${errorMessage(err)}`),
  });
  const source = current?.citations[0];
  return (
    <div className={styles.toolBody} aria-busy={write.isPending}>
      {current ? (
        <>
          <p className={styles.practiceQuestion} data-testid="similar-question">{current.question}</p>
          {source ? <p className={styles.toolHint}>Written from {source.doc}{source.page ? `, ${pageLabel(source.page, null, true)}` : ""}. The answer stays hidden until you ask for the evidence.</p> : null}
        </>
      ) : (
        <p className={styles.toolHint}>A new question on the same idea, from the same passages. Uses one model call.</p>
      )}
      <div className={styles.toolActions}>
        {current ? (
          <Button size="sm" disabled={busy} onClick={() => onPractise(turn, current.question)}>
            <PenLine className="h-4 w-4" aria-hidden="true" /> Try this question
          </Button>
        ) : null}
        <Button variant={current ? "ghost" : "secondary"} size="sm" aria-disabled={write.isPending || undefined} onClick={() => { if (!write.isPending) write.mutate(); }}>
          {write.isPending ? <Spinner /> : current ? <RefreshCw className="h-4 w-4" aria-hidden="true" /> : <Shuffle className="h-4 w-4" aria-hidden="true" />}
          {write.isPending ? "Writing a question…" : current ? "Another example" : "Write a similar question"}
        </Button>
      </div>
      {write.isError ? <ErrorNotice>{errorMessage(write.error)}</ErrorNotice> : null}
    </div>
  );
}

/** The same idea at another level, from the same passages. Each level is fetched once. */
function Different({ turn, onExplanation, announce }: { turn: Turn; onExplanation: (turn: Turn, level: EliLevel, explanation: Explanation) => void; announce: (m: string) => void }) {
  const id = useId();
  const [level, setLevel] = useState<EliLevel>("ELI5");
  const shown = turn.explanations?.[level];
  const explain = useMutation({
    mutationFn: async (l: EliLevel) => ({ level: l, res: unwrap(await api.http.POST("/api/v1/adaptive", { body: { question: turn.question, level: l, context: toPassages(turn.chunks) } })) }),
    onSuccess: ({ level: l, res }) => {
      onExplanation(turn, l, { answer: res.answer, warning: res.warning ?? undefined });
      announce("Explanation ready");
    },
    onError: (err) => announce(`Could not explain it another way: ${errorMessage(err)}`),
  });
  return (
    <div className={styles.toolBody} aria-busy={explain.isPending}>
      <div className={styles.toolActions}>
        <div className={styles.inlineField}>
          <Label htmlFor={`${id}-level`}>Level</Label>
          <Select id={`${id}-level`} value={level} onChange={(e) => setLevel(e.target.value as EliLevel)}>
            {EXPLAIN_LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </Select>
        </div>
        {shown ? null : (
          <Button variant="secondary" size="sm" aria-disabled={explain.isPending || undefined} onClick={() => { if (!explain.isPending) explain.mutate(level); }}>
            {explain.isPending ? <Spinner /> : null}
            {explain.isPending ? "Explaining…" : "Explain it this way"}
          </Button>
        )}
      </div>
      {explain.isError ? <ErrorNotice>{errorMessage(explain.error)}</ErrorNotice> : null}
      {shown ? (
        <div className={styles.explanation} data-testid="different-explanation" tabIndex={0} role="region" aria-label={`Explanation, ${EXPLAIN_LEVELS.find((l) => l.value === level)?.label}`}>
          <Markdown>{shown.answer}</Markdown>
          <p className={styles.toolHint}>{shown.warning ? "The model was unavailable, so this is a plain excerpt from the passage." : "From the same passages. Its citations are not checked, so compare it with the source."}</p>
        </div>
      ) : null}
    </div>
  );
}

/** Three opt-in tools, closed by default so they never push the answer or feedback out of view. */
export function UnderstandingTools({ turn, busy, onSaveNote, onSimilar, onExplanation, onPractise, announce }: {
  turn: Turn;
  busy: boolean;
  onSaveNote: (turn: Turn, note: string) => Promise<NoteSaved>;
  onSimilar: (turn: Turn, example: SimilarExample) => void;
  onExplanation: (turn: Turn, level: EliLevel, explanation: Explanation) => void;
  onPractise: (turn: Turn, question: string) => void;
  announce: (message: string) => void;
}) {
  const grounded = turn.chunks.length > 0;
  return (
    <div className={styles.tools}>
      <details className={styles.tool}>
        <summary>In your own words{turn.note ? <span className={styles.toolState}>saved</span> : null}</summary>
        <OwnWords turn={turn} onSaveNote={onSaveNote} announce={announce} />
      </details>
      {grounded ? (
        <details className={styles.tool}>
          <summary>Similar example{turn.similar?.length ? <span className={styles.toolState}>ready</span> : null}</summary>
          <Similar turn={turn} busy={busy} onSimilar={onSimilar} onPractise={onPractise} announce={announce} />
        </details>
      ) : null}
      {grounded ? (
        <details className={styles.tool}>
          <summary>Different explanation</summary>
          <Different turn={turn} onExplanation={onExplanation} announce={announce} />
        </details>
      ) : null}
    </div>
  );
}
