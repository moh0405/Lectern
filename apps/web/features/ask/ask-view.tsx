"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, BookOpen, CloudOff, FileText, Link2, MessageSquare, Plus, Send, SlidersHorizontal, Trash2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { EmptyState } from "@/components/ui/feedback";
import { useLocalDocs } from "@/lib/browser-rag/use-local-docs";
import { useDemo } from "@/lib/demo";
import { api, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ATTEMPT_FORMATS, CODE_LANGUAGES, feedbackMessage, MAX_ATTEMPT } from "./attempt";
import type { Selection } from "./citation-chip";
import { linkCitations, type CiteRef } from "./citations";
import { finishedMessage, groundingOf } from "./grounding";
import { InlinePassage } from "./inline-passage";
import { NotesPanel } from "./notes-panel";
import type { AttemptFormat, Mode, Turn } from "./session";
import { SourceMargin } from "./source-margin";
import { TraceLine } from "./trace-line";
import { TurnCard } from "./turn-card";
import { NARROW_QUERY, prefersReducedMotion, useMedia } from "./use-media";
import { useAskSession } from "./use-ask-session";
import styles from "./ask.module.css";

const MODES: { value: "" | Mode; label: string }[] = [
  { value: "", label: "Default" },
  { value: "eli5", label: "ELI5 (simple)" },
  { value: "technical", label: "Technical" },
  { value: "interview", label: "Interview prep" },
  { value: "summary", label: "Quick summary" },
];

type Approach = "answer" | "guided" | "try";
const APPROACHES: { value: Approach; label: string; description: string }[] = [
  { value: "answer", label: "Answer", description: "A cited answer straight away." },
  { value: "guided", label: "Guided", description: "Hints first, then the cited answer when you ask." },
  { value: "try", label: "Try first", description: "Write your own attempt and get feedback checked against your sources, then the answer when you ask." },
];

const STARTERS = ["Explain dynamic programming", "What is a hash table?", "Difference between BFS and DFS", "How does quicksort work?"];

/** The longest question the server accepts, and the shorter limit of a passage-only search. */
const MAX_QUESTION = 2000;
const MAX_SEARCH = 500;

const STEPS = [
  { id: "question", label: "Question" },
  { id: "evidence", label: "Evidence" },
  { id: "understanding", label: "Understanding" },
] as const;
type Step = (typeof STEPS)[number]["id"];

/** Links from a finished answer into the study tools, carrying the question so the tool opens ready to run. */
export function goFurtherLinks(question: string): { href: string; label: string }[] {
  const q = question.trim();
  const topic = encodeURIComponent(q.slice(0, 200)); // the topic fields take up to 200 characters
  const full = encodeURIComponent(q);
  return [
    { href: `/concept-map?topic=${topic}`, label: "Concept map of this topic" },
    { href: `/compare?topic=${topic}`, label: "Compare your sources" },
    { href: `/work-it-out?question=${full}`, label: "Work it out with hints" },
  ];
}

/**
 * Put `?q=` into the composer (the command palette's "Ask: …" and the Insights rows link here), then drop it
 * from the address so a reload does not bring it back. It never sends the question.
 */
function QueryPrefill({ onPrefill }: { onPrefill: (q: string) => void }) {
  const q = useSearchParams()?.get("q")?.trim().slice(0, MAX_QUESTION) ?? "";
  useEffect(() => {
    if (!q) return;
    onPrefill(q);
    const url = new URL(window.location.href);
    url.searchParams.delete("q");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  }, [q, onPrefill]);
  return null;
}

/** Open the first citation that has a passage; otherwise the best retrieved passage. */
function defaultSelection(turn: Turn | undefined, refs: CiteRef[]): Selection {
  const first = refs.find((r) => r.chunk !== null);
  if (first) return { ref: first.id, chunk: first.chunk };
  return { ref: null, chunk: turn?.chunks.length ? 0 : null };
}

/** Height of what is stuck to the top of the window on narrow screens: the site header and the steps bar. */
function stickyTop(): number {
  const header = document.querySelector(".desk-header")?.getBoundingClientRect().height ?? 0;
  const steps = document.querySelector("[data-steps-bar]")?.getBoundingClientRect().height ?? 0;
  return header + steps;
}

function Library({ turns, activeId, onPick, onClear, demo }: { turns: Turn[]; activeId?: string; onPick: (id: string) => void; onClear: () => void; demo: boolean }) {
  const shared = useQuery({ queryKey: ["documents"], queryFn: async () => unwrap(await api.http.GET("/api/v1/documents")), staleTime: 60_000 });
  const mine = useLocalDocs();
  const [confirming, setConfirming] = useState(false);
  const docs = [
    ...(mine.data ?? []).map((d) => ({ key: `mine-${d.id}`, name: d.name, note: `${plural(d.pages, "page")} · in this browser` })),
    ...(shared.data?.documents ?? []).map((d) => ({ key: d.source_key, name: d.docs[0] ?? d.source_key, note: `${plural(d.chunks, "passage")}${demo ? " · shared textbook" : ""}` })),
  ];
  const shown = docs.slice(0, 6);
  useEffect(() => {
    if (confirming) document.getElementById("ask-clear-confirm")?.focus();
  }, [confirming]);
  const cancel = () => {
    setConfirming(false);
    requestAnimationFrame(() => document.getElementById("ask-clear")?.focus());
  };
  return (
    <aside className={styles.library} aria-label="Your library">
      {/* Not a heading: the page's h1 ("Ask") comes later in the reading order. */}
      <p className={styles.libraryHead}>Your library</p>
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
          {confirming ? (
            <div
              className={styles.confirm}
              role="group"
              aria-label="Clear history?"
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  e.stopPropagation();
                  cancel();
                }
              }}
            >
              <p>
                Delete all {plural(turns.length, "question")} and {turns.length === 1 ? "its answer" : "their answers"} from this browser{demo ? "" : " and your saved history on the server"}? Flashcards and sources are kept.
              </p>
              <div className={styles.confirmActions}>
                <Button
                  id="ask-clear-confirm"
                  variant="danger"
                  size="sm"
                  onClick={() => {
                    setConfirming(false);
                    onClear();
                  }}
                >
                  Confirm clear
                </Button>
                <Button variant="ghost" size="sm" onClick={cancel}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button id="ask-clear" variant="ghost" size="sm" onClick={() => setConfirming(true)} className={styles.clearSession}>
              <Trash2 className="h-4 w-4" aria-hidden="true" /> Clear history
            </Button>
          )}
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
  const { turns, ask, nextHint, retryHints, retryFeedback, showEvidence, stop, remove, clear, busy } = useAskSession();
  const [approach, setApproach] = useState<Approach>("answer");
  const guided = approach === "guided";
  const trying = approach === "try";
  const [attempt, setAttempt] = useState("");
  const [attemptFormat, setAttemptFormat] = useState<AttemptFormat>("steps");
  const [language, setLanguage] = useState(CODE_LANGUAGES[0]!);
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
  const [inlineFor, setInlineFor] = useState<string | null>(null);
  const [trace, setTrace] = useState(true);
  const [step, setStep] = useState<Step>("question");
  const [announcement, setAnnouncement] = useState("");
  const [busyHint, setBusyHint] = useState(false);
  const [reveal, setReveal] = useState(0);
  const focusAfterRemove = useRef(false);
  const deskRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const advancedRef = useRef<HTMLDetailsElement>(null);
  const narrow = useMedia(NARROW_QUERY);
  // In the public demo a visitor can ask about documents kept in their own browser. Once they have added some, default to them.
  const demo = useDemo();
  const myDocs = useLocalDocs();
  const hasMine = demo && (myDocs.data?.length ?? 0) > 0;
  const [pickedSource, setPickedSource] = useState<"shared" | "mine" | null>(null);
  const local = hasMine && (pickedSource ?? "mine") === "mine";

  // Retry a failed stats call quickly, so a slow or cold first response settles into the empty or offline state promptly.
  const stats = useQuery({ queryKey: ["stats"], queryFn: async () => unwrap(await api.http.GET("/api/v1/stats")), retryDelay: (n) => Math.min(300 * 2 ** n, 1200) });
  const models = useQuery({
    queryKey: ["models"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/models")),
    enabled: advancedOpen && !demo,
    retry: false, // 503 without a server key: fall back to a free-text field
    staleTime: 10 * 60_000,
  });
  const suggestions = useQuery({
    queryKey: ["suggestions"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/suggestions", { params: { query: { n: 4 } } })),
    enabled: (stats.data?.chunks ?? 0) > 0,
    staleTime: 5 * 60_000,
  });

  /** Say something once through the page's status region (cleared first, so a repeat is read again). */
  const announce = useCallback((message: string) => {
    setAnnouncement("");
    window.setTimeout(() => setAnnouncement(message), 60);
  }, []);

  // The desk shows one question at a time: the newest, unless an earlier one was picked from the session list.
  const active = turns.find((t) => t.id === activeId) ?? turns[0];
  // Linked once here and shared with the answer (chips) and the source margin, so both use the same ids.
  const linked = useMemo(() => (active?.status === "done" ? linkCitations(active.answer, active.citations, active.chunks) : null), [active]);
  const refs = useMemo(() => linked?.refs ?? [], [linked]);
  const selection = picked && picked.turnId === active?.id ? picked.selection : defaultSelection(active, refs);
  const inlineOpen = narrow && active !== undefined && inlineFor === active.id;
  const scope = demo && active ? (active.local ? "In this browser" : "Shared library") : undefined;
  const grounding = groundingOf(active);
  const finished = active?.status === "done" && Boolean(active.answer);
  const showSteps = finished || Boolean(active?.guided) || Boolean(active?.attempt);
  const showUnderstanding = finished && grounding.kind !== "not-found";

  const select = (s: Selection) => {
    if (!active) return;
    setPicked({ turnId: active.id, selection: s });
    if (narrow) setInlineFor(active.id);
    const ref = s.ref !== null ? refs[s.ref] : undefined;
    const chunk = ref ? ref.chunk : s.chunk;
    if (chunk !== null && chunk !== undefined) announce(`Passage ${chunk + 1} opened ${narrow ? "below the answer" : "in the source margin"}`);
    else if (ref) announce(ref.status === "ok" ? "Citation opened: verified, but its passage is not listed" : "Citation opened: it could not be checked");
  };
  const closeInline = () => {
    setInlineFor(null);
    const chip = selection.ref !== null ? document.getElementById(`cite-chip-${selection.ref}`) : null;
    requestAnimationFrame(() => (chip ?? document.querySelector<HTMLElement>("[data-turn-heading]"))?.focus());
  };

  // Announce when a question finishes: how many citations were checked, or that it stopped or failed.
  const statuses = useRef(new Map<string, Turn["status"]>());
  useEffect(() => {
    const seen = statuses.current;
    for (const t of turns) {
      const before = seen.get(t.id);
      if (before === "streaming" && t.status !== "streaming") announce(t.attempt && !t.attempt.evidenceStarted ? (t.status === "done" && t.attempt.feedback ? feedbackMessage(t.attempt.feedback) : t.status === "stopped" ? "Feedback stopped." : "Feedback unavailable. Retry or show the evidence.") : t.guided && !t.guided.evidenceStarted ? (t.status === "done" ? "Guided hints ready. Reveal hints or show the evidence." : t.status === "stopped" ? "Guided hints stopped." : "Guided hints unavailable. Retry or show the evidence.") : finishedMessage(t));
      seen.set(t.id, t.status);
    }
  }, [turns, announce]);

  // The site header is sticky; the steps bar sticks just below it on narrow screens.
  useLayoutEffect(() => {
    const header = document.querySelector(".desk-header");
    const desk = deskRef.current;
    if (!header || !desk) return;
    const set = () => desk.style.setProperty("--ask-sticky-top", `${Math.round(header.getBoundingClientRect().height)}px`);
    set();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(set);
    ro.observe(header);
    return () => ro.disconnect();
  }, []);

  // Bring the new or picked question into view: the answer column on wide screens, the window when the columns stack.
  useEffect(() => {
    if (!reveal) return;
    const frame = requestAnimationFrame(() => {
      if (window.matchMedia?.(NARROW_QUERY).matches) {
        const el = document.querySelector('[data-step="question"]');
        if (el) window.scrollTo({ top: Math.max(0, el.getBoundingClientRect().top + window.scrollY - stickyTop() - 8), behavior: prefersReducedMotion() ? "auto" : "smooth" });
      } else scrollRef.current?.scrollTo?.({ top: 0 });
    });
    return () => cancelAnimationFrame(frame);
  }, [reveal]);

  // After Remove, focus the question now on the desk, or the page title when none is left.
  useEffect(() => {
    if (!focusAfterRemove.current) return;
    focusAfterRemove.current = false;
    (document.querySelector<HTMLElement>("[data-turn-heading]") ?? document.getElementById("ask-title"))?.focus();
  }, [turns]);

  // Mark the step whose section is at the top of the reading area, watching the column (wide) or the window (narrow).
  useEffect(() => {
    if (!showSteps || typeof IntersectionObserver === "undefined") return;
    const column = scrollRef.current;
    if (!column) return;
    const root = narrow ? null : column;
    const top = () => (root ? root.getBoundingClientRect().top : stickyTop()) + 120;
    const compute = () => {
      let current: Step = "question";
      for (const s of STEPS) {
        const el = column.querySelector(`[data-step="${s.id}"]`);
        if (el && el.getBoundingClientRect().top <= top()) current = s.id;
      }
      setStep(current);
    };
    const thresholds = Array.from({ length: 21 }, (_, i) => i / 20);
    const io = new IntersectionObserver(compute, { root, threshold: thresholds });
    column.querySelectorAll("[data-step]").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [showSteps, narrow, active?.id]);

  // Grow the question box with its text where CSS `field-sizing` is not supported.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el || (typeof CSS !== "undefined" && CSS.supports?.("field-sizing", "content"))) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight + 2, 220)}px`;
  }, [question]);

  const prefill = useCallback((q: string) => {
    setQuestion(q);
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (!el) return;
      el.focus({ preventScroll: true });
      el.setSelectionRange(q.length, q.length);
    });
  }, []);

  const offline = stats.isError;
  const searchOnly = approach === "answer" && retrievalOnly;
  const limit = searchOnly ? MAX_SEARCH : MAX_QUESTION;
  const attemptReady = !trying || (attempt.trim().length > 0 && attempt.length <= MAX_ATTEMPT);
  const formatInfo = ATTEMPT_FORMATS.find((f) => f.value === attemptFormat)!;
  const length = question.trim().length;
  const overLimit = question.length > limit;
  const nearLimit = question.length > limit * 0.8;

  const submit = (text: string) => {
    const q = text.trim();
    if (busy) {
      setBusyHint(true);
      announce("An answer is still being written. Wait for it, or stop it, before asking again.");
      return;
    }
    if (q.length < 3 || offline || q.length > limit) return;
    if (trying && !attemptReady) {
      announce("Write your attempt first, then check it.");
      document.getElementById("attempt")?.focus();
      return;
    }
    setActiveId(null);
    setPicked(null);
    setInlineFor(null);
    setStep("question");
    if (advancedRef.current?.open) advancedRef.current.open = false; // the panel floats over the answer
    announce(trying ? "Checking your attempt against your sources…" : local ? "Searching your browser documents…" : "Searching your material…");
    void ask({ question: q, mode: mode || undefined, k, temperature, model: demo ? undefined : model.trim() || undefined, showPrompt: !demo && showPrompt, retrievalOnly: searchOnly, guided, local, agent: agentic,
      attempt: trying ? { text: attempt, format: attemptFormat, language: attemptFormat === "code" ? language : undefined } : undefined });
    setReveal((n) => n + 1);
    setQuestion("");
    if (trying) setAttempt("");
  };
  useEffect(() => {
    if (!busyHint) return;
    const t = window.setTimeout(() => setBusyHint(false), 5000);
    return () => window.clearTimeout(t);
  }, [busyHint, busy]);

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
    if (!target) return;
    const behavior = prefersReducedMotion() ? "auto" : "smooth";
    if (narrow) window.scrollTo({ top: Math.max(0, target.getBoundingClientRect().top + window.scrollY - stickyTop() - 8), behavior });
    else target.scrollIntoView({ behavior, block: "start" });
  };

  const empty = stats.isSuccess && (stats.data?.chunks ?? 0) === 0 && !hasMine;
  const chips = suggestions.data?.questions.length ? suggestions.data.questions : STARTERS;
  const traceable = refs.some((r) => r.chunk !== null);
  const askAgain = (t: Turn, extra: { local?: boolean } = {}) =>
    void ask({ question: t.question, mode: t.mode, k, temperature, model: demo ? undefined : model.trim() || undefined, noCache: true, local: extra.local ?? Boolean(t.local), agent: t.agent });

  return (
    <div className={styles.desk} ref={deskRef}>
      <Library
        turns={turns}
        activeId={active?.id}
        demo={demo}
        onClear={() => {
          clear();
          setActiveId(null);
          announce("History cleared");
          requestAnimationFrame(() => document.getElementById("ask-title")?.focus());
        }}
        onPick={(id) => {
          setActiveId(id);
          setInlineFor(null);
          setStep("question");
          setReveal((n) => n + 1);
        }}
      />

      <section className={styles.center} aria-labelledby="ask-title">
        <div className={styles.toolbar}>
          <div className={styles.crumbs}>
            <BookOpen aria-hidden="true" />
            <h1 id="ask-title" tabIndex={-1}>
              Ask
            </h1>
            <span aria-hidden="true">/</span>
            <span>{active ? "A study session" : "A new question"}</span>
          </div>
          {active && traceable ? (
            <button type="button" className={styles.traceToggle} aria-pressed={trace} onClick={() => setTrace(!trace)}>
              <Link2 aria-hidden="true" /> {trace ? "Trace on" : "Trace off"}
            </button>
          ) : null}
        </div>

        {active && showSteps ? (
          <nav className={styles.steps} aria-label="Steps" data-steps-bar>
            {STEPS.filter((s) => s.id !== "understanding" || showUnderstanding).map((s, i) => (
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

        <div className={styles.scroll} ref={scrollRef} data-desk-scroll>
          {active ? (
            <>
              <div data-step="question" className={styles.turnAnchor}>
                <TurnCard
                  key={active.id}
                  turn={active}
                  busy={busy}
                  selection={selection}
                  onSelect={select}
                  linked={linked}
                  announce={announce}
                  narrow={narrow}
                  scope={scope}
                  inlinePassage={inlineOpen ? <InlinePassage turn={active} refs={refs} selection={selection} onClose={closeInline} scope={scope} /> : null}
                  onStop={() => stop(active.id)}
                  onRemove={() => {
                    remove(active.id);
                    setActiveId(null);
                    focusAfterRemove.current = true;
                    announce("Question removed");
                  }}
                  onFresh={() => {
                    const prelude = active.attempt ?? active.guided;
                    if (!prelude) askAgain(active);
                    else if (prelude.evidenceStarted) void showEvidence(active);
                    else if (active.attempt) void retryFeedback(active);
                    else void retryHints(active);
                  }}
                  onNextHint={() => nextHint(active.id)}
                  onEvidence={() => void showEvidence(active)}
                  onSearchShared={
                    active.error?.code === "no_local_match"
                      ? () => {
                          setPickedSource("shared");
                          askAgain(active, { local: false });
                          setReveal((n) => n + 1);
                        }
                      : undefined
                  }
                />
              </div>
              {showUnderstanding ? (
                <section data-step="understanding" className={styles.understanding} aria-labelledby="understanding-title">
                  <p className="eyebrow">Understanding / something to keep</p>
                  <h2 id="understanding-title">Make the idea yours.</h2>
                  <p className={styles.understandingLead}>Keep the source open, then turn what you read into something you can review later.</p>
                  <div className={styles.nextSteps}>
                    <Link href="/study">
                      Review your flashcards <ArrowUpRight aria-hidden="true" />
                    </Link>
                  </div>
                  {active && active.chunks.length > 0 ? (
                    <div className={styles.goFurther} data-testid="go-further">
                      <h3 id="go-further-title" className="eyebrow">
                        Go further
                      </h3>
                      <ul aria-labelledby="go-further-title">
                        {goFurtherLinks(active.question).map((l) => (
                          <li key={l.href}>
                            <Link href={l.href}>
                              {l.label} <ArrowUpRight aria-hidden="true" />
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </section>
              ) : null}
              {/* Notes cover the whole session, so they stay available whichever question is on the desk. */}
              <div className={styles.sessionNotes}>
                <NotesPanel turns={turns} />
              </div>
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
              {offline ? (
                <div className={styles.offline}>
                  <CloudOff aria-hidden="true" />
                  <div>
                    <p className={styles.offlineTitle}>Can&apos;t reach Lectern right now</p>
                    <p>Your library and answers come from the Lectern server, which is not answering. Check your connection, then try again.</p>
                    <Button variant="secondary" size="sm" className="mt-3" disabled={stats.isFetching} onClick={() => void stats.refetch()}>
                      {stats.isFetching ? "Trying again…" : "Retry"}
                    </Button>
                  </div>
                </div>
              ) : empty ? (
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
                    <button type="button" onClick={() => submit(c)} disabled={busy || offline} className={styles.starter}>
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
          <Segmented legend="How Lectern responds" name="approach" options={APPROACHES} value={approach} onChange={setApproach} className={styles.approach} fill={narrow} />
          <div className={styles.composerBox}>
            <label htmlFor="question" className="sr-only">
              Your question
            </label>
            <Textarea
              ref={inputRef}
              id="question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={active ? (narrow ? "Ask a follow-up…" : "Ask a follow-up, or pull on a new thread…") : "What would you like to understand?"}
              maxLength={limit}
              rows={1}
              aria-describedby={nearLimit ? "question-count" : undefined}
              className={styles.questionInput}
            />
            {trying ? (
              <div className={styles.attemptPanel} data-format={attemptFormat}>
                <div className={styles.attemptControls}>
                  <Segmented legend="Attempt format" name="attempt-format" options={ATTEMPT_FORMATS.map((f) => ({ value: f.value, label: f.label }))} value={attemptFormat} onChange={setAttemptFormat} />
                  {attemptFormat === "code" ? (
                    <div className={styles.inlineField}>
                      <Label htmlFor="attempt-language">Language</Label>
                      <Select id="attempt-language" value={language} onChange={(e) => setLanguage(e.target.value)}>
                        {CODE_LANGUAGES.map((l) => (
                          <option key={l} value={l}>{l}</option>
                        ))}
                      </Select>
                    </div>
                  ) : null}
                </div>
                <label htmlFor="attempt" className={styles.attemptLabel}>
                  Your attempt <span>{formatInfo.hint}</span>
                </label>
                <Textarea
                  id="attempt"
                  value={attempt}
                  onChange={(e) => setAttempt(e.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder={attemptFormat === "steps" ? "Write what you understand so far, one step per line" : "Write what you understand so far"}
                  maxLength={MAX_ATTEMPT}
                  rows={attemptFormat === "short_answer" ? 3 : 4}
                  spellCheck={attemptFormat !== "code"}
                  wrap={attemptFormat === "code" ? "off" : undefined}
                  className={styles.attemptInput}
                  data-code={attemptFormat === "code" || undefined}
                />
              </div>
            ) : null}
            <div className={styles.composerBar}>
              <details
                ref={advancedRef}
                className={styles.advanced}
                onToggle={(e) => setAdvancedOpen(e.currentTarget.open)}
                onKeyDown={(e) => {
                  if (e.key === "Escape" && advancedRef.current?.open) {
                    e.stopPropagation();
                    advancedRef.current.open = false;
                    advancedRef.current.querySelector("summary")?.focus();
                  }
                }}
              >
                <summary>
                  <SlidersHorizontal aria-hidden="true" />
                  <span>Advanced</span>
                  <span className={styles.advancedHint}>Adjust the search and answer</span>
                </summary>
                <div className={styles.advancedPanel}>
                  <div className={styles.advancedGrid}>
                    <div>
                      <Label htmlFor="mode">Style</Label>
                      <Select id="mode" value={mode} onChange={(e) => setMode(e.target.value as "" | Mode)}>
                        {MODES.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="k">Passages</Label>
                      <Select id="k" value={k} onChange={(e) => setK(Number(e.target.value))}>
                        {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <label className={styles.check}>
                      <input type="checkbox" checked={agentic && !local && !retrievalOnly} onChange={(e) => setAgentic(e.target.checked)} disabled={local || retrievalOnly} className="mt-1 accent-[var(--color-accent)]" />
                      <span>
                        <span className="font-medium">Agentic mode</span>{" "}
                        <span className="text-muted">
                          rewrites the search, checks the passages and re-checks the citations (slower, up to 6 model calls{demo ? ", each counted against the demo's daily limit" : ""})
                          {local ? ". Not available for your own documents." : ""}
                        </span>
                      </span>
                    </label>
                    <div>
                      <Label htmlFor="temperature">Temperature: {temperature.toFixed(2)}</Label>
                      <input id="temperature" type="range" min={0} max={1} step={0.05} value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} className="w-full accent-[var(--color-accent)]" />
                    </div>
                    {demo ? null : (
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
                    )}
                    <label className={styles.check}>
                      <input type="checkbox" checked={retrievalOnly} onChange={(e) => setRetrievalOnly(e.target.checked)} className="accent-[var(--color-accent)]" />
                      <span>
                        Only show matching passages (skip the model)
                        <span className={styles.checkNote}>Searches take questions of up to {MAX_SEARCH} characters.</span>
                      </span>
                    </label>
                    {demo ? null : (
                      <label className={styles.check}>
                        <input type="checkbox" checked={showPrompt} onChange={(e) => setShowPrompt(e.target.checked)} disabled={retrievalOnly} className="accent-[var(--color-accent)]" />
                        Show the prompt sent to the model
                      </label>
                    )}
                  </div>
                </div>
              </details>
              {hasMine ? (
                <div className={styles.inlineField}>
                  <Label htmlFor="source">Search in</Label>
                  <Select id="source" value={local ? "mine" : "shared"} onChange={(e) => setPickedSource(e.target.value as "shared" | "mine")}>
                    <option value="mine">My documents</option>
                    <option value="shared">Shared textbooks</option>
                  </Select>
                </div>
              ) : null}
              {nearLimit ? (
                <span id="question-count" className={styles.counter} data-over={overLimit ? "true" : undefined}>
                  {question.length} / {limit}
                  <span className="sr-only"> characters</span>
                </span>
              ) : null}
              <Button type="submit" disabled={busy || offline || length < 3 || overLimit || !attemptReady} className={styles.askButton}>
                <Send className="h-4 w-4" aria-hidden="true" /> {trying ? "Check my attempt" : "Ask"}
              </Button>
            </div>
          </div>
          <div className={styles.composerFoot}>
            {busyHint && busy ? (
              <span className={styles.footHint}>An answer is still being written. Wait for it, or stop it, then ask again.</span>
            ) : offline ? (
              <span className={styles.footHint}>Can&apos;t reach Lectern right now, so questions can&apos;t be sent.</span>
            ) : overLimit ? (
              <span className={styles.footHint}>A passage-only search takes up to {MAX_SEARCH} characters. Shorten the question or turn the option off.</span>
            ) : (
              <span>{local ? "Searching your browser documents" : "Searching your study material"}</span>
            )}
            <span className={styles.kbdHint}>
              <kbd>⌘ / Ctrl + Enter</kbd> to send
            </span>
          </div>
        </form>
      </section>

      <aside className={cn(styles.margin, "paper")} aria-label="Source margin">
        <SourceMargin turn={active} refs={refs} selection={selection} onSelect={select} scope={scope} />
      </aside>

      <TraceLine enabled={Boolean(active) && trace && traceable && !narrow} version={`${active?.id}:${selection.ref}:${selection.chunk}`} />

      <Suspense fallback={null}>
        <QueryPrefill onPrefill={prefill} />
      </Suspense>

      {/* One status region for the whole desk; the streaming answer itself is not a live region. */}
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>
    </div>
  );
}
