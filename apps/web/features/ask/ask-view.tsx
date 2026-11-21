"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, BookOpen, FileText, Link2, MessageSquare, Plus, Send, SlidersHorizontal, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/field";
import { EmptyState } from "@/components/ui/feedback";
import { useLocalDocs } from "@/lib/browser-rag/use-local-docs";
import { useDemo } from "@/lib/demo";
import { api, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import { linkCitations, type CiteRef } from "./citations";
import { NotesPanel } from "./notes-panel";
import type { Mode, Turn } from "./session";
import { SourceMargin } from "./source-margin";
import { TraceLine } from "./trace-line";
import { TurnCard, type Selection } from "./turn-card";
import { useAskSession } from "./use-ask-session";
import styles from "./ask.module.css";

const MODES: { value: "" | Mode; label: string }[] = [
  { value: "", label: "Default" },
  { value: "eli5", label: "ELI5 (simple)" },
  { value: "technical", label: "Technical" },
  { value: "interview", label: "Interview prep" },
  { value: "summary", label: "Quick summary" },
];

const STARTERS = ["Explain dynamic programming", "What is a hash table?", "Difference between BFS and DFS", "How does quicksort work?"];

const STEPS = [
  { id: "question", label: "Question" },
  { id: "evidence", label: "Evidence" },
  { id: "understanding", label: "Understanding" },
] as const;
type Step = (typeof STEPS)[number]["id"];

/** Open the first citation that has a passage; otherwise the best retrieved passage. */
function defaultSelection(turn: Turn | undefined, refs: CiteRef[]): Selection {
  const first = refs.find((r) => r.chunk !== null);
  if (first) return { ref: first.id, chunk: first.chunk };
  return { ref: null, chunk: turn?.chunks.length ? 0 : null };
}

function Library({ turns, activeId, onPick, onClear, demo }: { turns: Turn[]; activeId?: string; onPick: (id: string) => void; onClear: () => void; demo: boolean }) {
  const shared = useQuery({ queryKey: ["documents"], queryFn: async () => unwrap(await api.http.GET("/api/v1/documents")), staleTime: 60_000 });
  const mine = useLocalDocs();
  const docs = [
    ...(mine.data ?? []).map((d) => ({ key: `mine-${d.id}`, name: d.name, note: `${plural(d.pages, "page")} · in this browser` })),
    ...(shared.data?.documents ?? []).map((d) => ({ key: d.source_key, name: d.docs[0] ?? d.source_key, note: `${plural(d.chunks, "passage")}${demo ? " · shared textbook" : ""}` })),
  ];
  const shown = docs.slice(0, 6);
  return (
    <aside className={styles.library} aria-label="Your library">
      <div className={styles.libraryHead}>
        <h2>Your library</h2>
      </div>
      <Link href="/sources" className={styles.addMaterial}>
        <Plus aria-hidden="true" /> Add material
      </Link>
      {shown.length ? (
        <>
          <p className={cn("eyebrow", styles.railLabel)}>Your material</p>
          <ul className={styles.docList}>
            {shown.map((d) => (
              <li key={d.key}>
                <FileText aria-hidden="true" />
                <span className="min-w-0">
                  <span className={styles.docName}>{d.name}</span>
                  <span className={styles.docNote}>{d.note}</span>
                </span>
              </li>
            ))}
          </ul>
          {docs.length > shown.length ? (
            <Link href="/sources" className={styles.moreDocs}>
              and {docs.length - shown.length} more in your library
            </Link>
          ) : null}
        </>
      ) : null}
      {turns.length ? (
        <>
          <p className={cn("eyebrow", styles.railLabel)} id="session-label">
            This session
          </p>
          <ul className={styles.sessionList} aria-labelledby="session-label">
            {turns.map((t) => (
              <li key={t.id}>
                <button type="button" aria-current={t.id === activeId ? "true" : undefined} onClick={() => onPick(t.id)}>
                  <MessageSquare aria-hidden="true" />
                  <span>{t.question}</span>
                </button>
              </li>
            ))}
          </ul>
          <Button variant="ghost" size="sm" onClick={onClear} className={styles.clearSession}>
            <Trash2 className="h-4 w-4" /> Clear session
          </Button>
        </>
      ) : null}
      <div className={styles.libraryFoot}>
        <strong>Learn from the source.</strong>
        <p>One place for the question, its evidence, and the next thing to learn.</p>
      </div>
    </aside>
  );
}

export function AskView() {
  const { turns, ask, stop, remove, clear, busy } = useAskSession();
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"" | Mode>("");
  const [k, setK] = useState(3);
  const [temperature, setTemperature] = useState(0.2);
  const [model, setModel] = useState("");
  const [showPrompt, setShowPrompt] = useState(false);
  const [retrievalOnly, setRetrievalOnly] = useState(false);
  const [agentic, setAgentic] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [picked, setPicked] = useState<{ turnId: string; selection: Selection } | null>(null);
  const [trace, setTrace] = useState(true);
  const [step, setStep] = useState<Step>("question");
  const scrollRef = useRef<HTMLDivElement>(null);
  // In the public demo a visitor can ask about documents kept in their own browser. Once they have added some, default to them.
  const demo = useDemo();
  const myDocs = useLocalDocs();
  const hasMine = demo && (myDocs.data?.length ?? 0) > 0;
  const [pickedSource, setPickedSource] = useState<"shared" | "mine" | null>(null);
  const local = hasMine && (pickedSource ?? "mine") === "mine";

  const stats = useQuery({ queryKey: ["stats"], queryFn: async () => unwrap(await api.http.GET("/api/v1/stats")) });
  const models = useQuery({
    queryKey: ["models"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/models")),
    enabled: advancedOpen,
    retry: false, // 503 without a server key: fall back to a free-text field
    staleTime: 10 * 60_000,
  });
  const suggestions = useQuery({
    queryKey: ["suggestions"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/suggestions", { params: { query: { n: 4 } } })),
    enabled: (stats.data?.chunks ?? 0) > 0,
    staleTime: 5 * 60_000,
  });

  // The desk shows one question at a time: the newest, unless an earlier one was picked from the session list.
  const active = turns.find((t) => t.id === activeId) ?? turns[0];
  const refs = useMemo(() => (active?.status === "done" ? linkCitations(active.answer, active.citations, active.chunks).refs : []), [active]);
  const selection = picked && picked.turnId === active?.id ? picked.selection : defaultSelection(active, refs);
  const select = (s: Selection) => active && setPicked({ turnId: active.id, selection: s });

  const submit = (text: string) => {
    const q = text.trim();
    if (q.length < 3 || busy) return;
    setActiveId(null);
    setPicked(null);
    setStep("question");
    scrollRef.current?.scrollTo({ top: 0 });
    void ask({ question: q, mode: mode || undefined, k, temperature, model: model.trim() || undefined, showPrompt, retrievalOnly, local, agent: agentic });
    setQuestion("");
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(question);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      submit(question);
    }
  };

  const goTo = (id: Step) => {
    setStep(id);
    const target = scrollRef.current?.querySelector(`[data-step="${id}"]`);
    target?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  };
  // Mark the step whose section has scrolled to the top of the column.
  const onScroll = () => {
    const root = scrollRef.current;
    if (!root) return;
    const top = root.getBoundingClientRect().top + 120;
    let current: Step = "question";
    for (const s of STEPS) {
      const el = root.querySelector(`[data-step="${s.id}"]`);
      if (el && el.getBoundingClientRect().top <= top) current = s.id;
    }
    if (current !== step) setStep(current);
  };

  const empty = (stats.data?.chunks ?? 0) === 0 && !stats.isPending;
  const chips = suggestions.data?.questions.length ? suggestions.data.questions : STARTERS;
  const traceable = refs.some((r) => r.chunk !== null);

  return (
    <div className={styles.desk}>
      <Library
        turns={turns}
        activeId={active?.id}
        demo={demo}
        onClear={clear}
        onPick={(id) => {
          setActiveId(id);
          setStep("question");
          scrollRef.current?.scrollTo({ top: 0 });
        }}
      />

      <section className={styles.center} aria-labelledby="ask-title">
        <div className={styles.toolbar}>
          <div className={styles.crumbs}>
            <BookOpen aria-hidden="true" />
            <h1 id="ask-title">Ask</h1>
            <span aria-hidden="true">/</span>
            <span>{active ? "A study session" : "A new question"}</span>
          </div>
          {active && traceable ? (
            <button type="button" className={styles.traceToggle} aria-pressed={trace} onClick={() => setTrace(!trace)}>
              <Link2 aria-hidden="true" /> {trace ? "Trace on" : "Trace off"}
            </button>
          ) : null}
        </div>

        {active ? (
          <nav className={styles.steps} aria-label="Steps">
            {STEPS.map((s, i) => (
              <span key={s.id} className={styles.stepItem}>
                {i > 0 ? <span className={styles.stepLine} aria-hidden="true" /> : null}
                <button type="button" aria-current={step === s.id ? "step" : undefined} onClick={() => goTo(s.id)}>
                  <span className={styles.stepNumber}>0{i + 1}</span>
                  {s.label}
                </button>
              </span>
            ))}
          </nav>
        ) : null}

        <div className={styles.scroll} ref={scrollRef} onScroll={onScroll} data-desk-scroll>
          {active ? (
            <>
              <div data-step="question">
                <TurnCard
                  key={active.id}
                  turn={active}
                  busy={busy}
                  selection={selection}
                  onSelect={select}
                  onStop={() => stop(active.id)}
                  onRemove={() => remove(active.id)}
                  onFresh={() => void ask({ question: active.question, mode: active.mode, k, temperature, model: model.trim() || undefined, noCache: true, local, agent: active.agent })}
                />
              </div>
              <section data-step="understanding" className={styles.understanding} aria-labelledby="understanding-title">
                <p className="eyebrow">Understanding / something to keep</p>
                <h2 id="understanding-title">Make the idea yours.</h2>
                <p className={styles.understandingLead}>Keep the source open, then turn what you read into something you can review later.</p>
                <div className={styles.nextSteps}>
                  <Link href="/study">
                    Review your flashcards <ArrowUpRight aria-hidden="true" />
                  </Link>
                  <Link href="/tutor?tool=socratic">
                    Work through it with guiding questions <ArrowUpRight aria-hidden="true" />
                  </Link>
                </div>
                <NotesPanel turns={turns} />
              </section>
            </>
          ) : (
            <div className={styles.opening}>
              <span className={styles.openingMark} aria-hidden="true">
                <BookOpen />
              </span>
              <p className="eyebrow">Your material. A clearer picture.</p>
              <h2 className={styles.openingTitle}>
                Ask a question.
                <br />
                Keep the source close.
              </h2>
              <p className={styles.openingLead}>Bring your material into the conversation. Every answer cites the passages it came from, and each citation opens beside the answer.</p>
              {empty ? (
                <div className={styles.openingEmpty}>
                  <EmptyState title="No study material yet">
                    <Link href="/sources" className="text-accent-2 underline">
                      Add a PDF, a YouTube lecture or a web page
                    </Link>{" "}
                    first, then ask questions about it.
                  </EmptyState>
                </div>
              ) : null}
              <p className={cn("eyebrow", styles.startersLabel)}>A place to start</p>
              <ul className={styles.starters}>
                {chips.map((c) => (
                  <li key={c}>
                    <button type="button" onClick={() => submit(c)} disabled={busy} className={styles.starter}>
                      {c}
                      <ArrowUpRight aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <form onSubmit={onSubmit} className={styles.composer}>
          <div className={styles.composerBox}>
            <div className={styles.questionLabel}>
              <Label htmlFor="question">Your question</Label>
              <span>{local ? "Searching your browser documents" : "Searching your study material"}</span>
            </div>
            <Textarea
              id="question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={active ? "Ask a follow-up, or pull on a new thread…" : "What would you like to understand?"}
              maxLength={2000}
              rows={2}
              className={styles.questionInput}
            />
            <div className={styles.composerBar}>
              {hasMine ? (
                <div className={styles.inlineField}>
                  <Label htmlFor="source">Search in</Label>
                  <Select id="source" value={local ? "mine" : "shared"} onChange={(e) => setPickedSource(e.target.value as "shared" | "mine")}>
                    <option value="mine">My documents (in this browser)</option>
                    <option value="shared">The shared textbooks</option>
                  </Select>
                </div>
              ) : null}
              <div className={styles.inlineField}>
                <Label htmlFor="mode">Style</Label>
                <Select id="mode" value={mode} onChange={(e) => setMode(e.target.value as "" | Mode)}>
                  {MODES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div className={styles.inlineField}>
                <Label htmlFor="k">Passages</Label>
                <Select id="k" value={k} onChange={(e) => setK(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              </div>
              <Button type="submit" disabled={busy || question.trim().length < 3} className={styles.askButton}>
                <Send className="h-4 w-4" /> Ask
              </Button>
            </div>
            <details className={styles.advanced} onToggle={(e) => setAdvancedOpen(e.currentTarget.open)}>
              <summary aria-label="Advanced">
                <SlidersHorizontal aria-hidden="true" /> Advanced
                <span>Adjust the search and answer</span>
              </summary>
              <div className={styles.advancedGrid}>
                <label className="flex items-start gap-2 text-sm">
                  <input type="checkbox" checked={agentic && !local && !retrievalOnly} onChange={(e) => setAgentic(e.target.checked)} disabled={local || retrievalOnly} className="mt-1 accent-[var(--color-accent)]" />
                  <span>
                    <span className="font-medium">Agentic mode</span>{" "}
                    <span className="text-muted">
                      rewrites the search, checks the passages and re-checks the citations (slower, up to 6 model calls)
                      {local ? ". Not available for your own documents." : ""}
                    </span>
                  </span>
                </label>
                <div>
                  <Label htmlFor="temperature">Temperature: {temperature.toFixed(2)}</Label>
                  <input id="temperature" type="range" min={0} max={1} step={0.05} value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} className="w-full accent-[var(--color-accent)]" />
                </div>
                <div>
                  <Label htmlFor="model">Model</Label>
                  {models.data ? (
                    <Select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
                      <option value="">Server default ({models.data.default})</option>
                      {models.data.models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <Input id="model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="server default" />
                  )}
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={retrievalOnly} onChange={(e) => setRetrievalOnly(e.target.checked)} className="accent-[var(--color-accent)]" />
                  Only show matching passages (skip the model)
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={showPrompt} onChange={(e) => setShowPrompt(e.target.checked)} disabled={retrievalOnly} className="accent-[var(--color-accent)]" />
                  Show the prompt sent to the model
                </label>
              </div>
            </details>
          </div>
          <div className={styles.composerFoot}>
            <span>Sources stay one click away.</span>
            <span>
              <kbd>⌘ / Ctrl + Enter</kbd> to send
            </span>
          </div>
        </form>
      </section>

      <aside className={cn(styles.margin, "paper")} aria-label="Source margin">
        <SourceMargin turn={active} refs={refs} selection={selection} onSelect={select} />
      </aside>

      <TraceLine enabled={Boolean(active) && trace && traceable} version={`${active?.id}:${selection.ref}:${selection.chunk}`} />
    </div>
  );
}
