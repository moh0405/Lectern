"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  BookOpen,
  Send,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/field";
import { EmptyState } from "@/components/ui/feedback";
import { useLocalDocs } from "@/lib/browser-rag/use-local-docs";
import { useDemo } from "@/lib/demo";
import { api, unwrap } from "@/lib/api";
import { NotesPanel } from "./notes-panel";
import type { Mode } from "./session";
import { TurnCard } from "./turn-card";
import { useAskSession } from "./use-ask-session";
import styles from "./ask.module.css";

const MODES: { value: "" | Mode; label: string }[] = [
  { value: "", label: "Default" },
  { value: "eli5", label: "ELI5 (simple)" },
  { value: "technical", label: "Technical" },
  { value: "interview", label: "Interview prep" },
  { value: "summary", label: "Quick summary" },
];

const STARTERS = [
  "Explain dynamic programming",
  "What is a hash table?",
  "Difference between BFS and DFS",
  "How does quicksort work?",
];

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
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // In the public demo a visitor can ask about documents kept in their own browser. Once they have added some, default to them.
  const demo = useDemo();
  const myDocs = useLocalDocs();
  const hasMine = demo && (myDocs.data?.length ?? 0) > 0;
  const [pickedSource, setPickedSource] = useState<"shared" | "mine" | null>(
    null,
  );
  const local = hasMine && (pickedSource ?? "mine") === "mine";

  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/stats")),
  });
  const models = useQuery({
    queryKey: ["models"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/models")),
    enabled: advancedOpen,
    retry: false, // 503 without a server key: fall back to a free-text field
    staleTime: 10 * 60_000,
  });
  const suggestions = useQuery({
    queryKey: ["suggestions"],
    queryFn: async () =>
      unwrap(
        await api.http.GET("/api/v1/suggestions", {
          params: { query: { n: 4 } },
        }),
      ),
    enabled: (stats.data?.chunks ?? 0) > 0,
    staleTime: 5 * 60_000,
  });

  const submit = (text: string) => {
    const q = text.trim();
    if (q.length < 3 || busy) return;
    void ask({
      question: q,
      mode: mode || undefined,
      k,
      temperature,
      model: model.trim() || undefined,
      showPrompt,
      retrievalOnly,
      local,
      agent: agentic,
    });
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

  const empty = (stats.data?.chunks ?? 0) === 0 && !stats.isPending;
  const chips = suggestions.data?.questions.length
    ? suggestions.data.questions
    : STARTERS;

  return (
    <div className={styles.workspace}>
      <div className={styles.masthead}>
        <p className={styles.eyebrow}>
          <BookOpen aria-hidden="true" /> YOUR RESEARCH DESK
        </p>
        <PageHeader
          title="Ask"
          description="Ask a question about your own material. Answers cite the passages they came from."
          actions={
            turns.length ? (
              <Button variant="ghost" size="sm" onClick={clear}>
                <Trash2 className="h-4 w-4" /> Clear session
              </Button>
            ) : undefined
          }
        />
      </div>

      {empty ? (
        <div className="mb-4">
          <EmptyState title="No study material yet">
            <Link href="/sources" className="text-accent-2 underline">
              Add a PDF, a YouTube lecture or a web page
            </Link>{" "}
            first, then ask questions about it.
          </EmptyState>
        </div>
      ) : null}

      <Card className={styles.composer}>
        <form onSubmit={onSubmit} className={styles.composerForm}>
          <div className={styles.questionField}>
            <div className={styles.composerHeading}>
              <Label htmlFor="question">Your question</Label>
              <span>
                {local ? "Your browser documents" : "Your study material"}
              </span>
            </div>
            <Textarea
              id="question"
              ref={inputRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="e.g. What is a linked list, and when would I use one?"
              maxLength={2000}
              rows={3}
            />
          </div>
          <div className={styles.starters}>
            <span className={styles.starterLabel}>A place to start</span>
            {chips.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => submit(c)}
                disabled={busy}
                className={styles.starter}
              >
                {c}
                <ArrowUpRight aria-hidden="true" />
              </button>
            ))}
          </div>
          {hasMine ? (
            <div>
              <Label htmlFor="source">Search in</Label>
              <Select
                id="source"
                value={local ? "mine" : "shared"}
                onChange={(e) =>
                  setPickedSource(e.target.value as "shared" | "mine")
                }
              >
                <option value="mine">My documents (in this browser)</option>
                <option value="shared">The shared textbooks</option>
              </Select>
            </div>
          ) : null}
          <div className={styles.composeControls}>
            <div>
              <Label htmlFor="mode">Style</Label>
              <Select
                id="mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as "" | Mode)}
              >
                {MODES.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="k">Passages</Label>
              <Select
                id="k"
                value={k}
                onChange={(e) => setK(Number(e.target.value))}
              >
                {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                type="submit"
                disabled={busy || question.trim().length < 3}
                className="w-full sm:w-auto"
              >
                <Send className="h-4 w-4" /> Ask
              </Button>
            </div>
          </div>
          <details
            className={styles.advanced}
            onToggle={(e) => setAdvancedOpen(e.currentTarget.open)}
          >
            <summary aria-label="Advanced">
              <SlidersHorizontal aria-hidden="true" /> Advanced
              <span>Adjust the search and answer</span>
            </summary>
            <div className={styles.advancedGrid}>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={agentic && !local && !retrievalOnly}
                  onChange={(e) => setAgentic(e.target.checked)}
                  disabled={local || retrievalOnly}
                  className="mt-1 accent-[var(--color-accent)]"
                />
                <span>
                  <span className="font-medium">Agentic mode</span>{" "}
                  <span className="text-muted">
                    rewrites the search, checks the passages and re-checks the
                    citations (slower, up to 6 model calls)
                    {local ? ". Not available for your own documents." : ""}
                  </span>
                </span>
              </label>

              <div>
                <Label htmlFor="temperature">
                  Temperature: {temperature.toFixed(2)}
                </Label>
                <input
                  id="temperature"
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="w-full accent-[var(--color-accent)]"
                />
              </div>
              <div>
                <Label htmlFor="model">Model</Label>
                {models.data ? (
                  <Select
                    id="model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                  >
                    <option value="">
                      Server default ({models.data.default})
                    </option>
                    {models.data.models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Input
                    id="model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="server default"
                  />
                )}
              </div>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={retrievalOnly}
                  onChange={(e) => setRetrievalOnly(e.target.checked)}
                  className="accent-[var(--color-accent)]"
                />
                Only show matching passages (skip the model)
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showPrompt}
                  onChange={(e) => setShowPrompt(e.target.checked)}
                  disabled={retrievalOnly}
                  className="accent-[var(--color-accent)]"
                />
                Show the prompt sent to the model
              </label>
            </div>
          </details>
          <div className={styles.composerFootnote}>
            <p>Follow the answer back to its sources.</p>
            <p>
              Press <kbd>Ctrl/⌘ + Enter</kbd> to send.
            </p>
          </div>
        </form>
      </Card>

      <div className={styles.conversation}>
        {turns.map((t) => (
          <TurnCard
            key={t.id}
            turn={t}
            busy={busy}
            onStop={() => stop(t.id)}
            onRemove={() => remove(t.id)}
            onFresh={() =>
              void ask({
                question: t.question,
                mode: t.mode,
                k,
                temperature,
                model: model.trim() || undefined,
                noCache: true,
                local,
                agent: t.agent,
              })
            }
          />
        ))}
        <NotesPanel turns={turns} />
      </div>
    </div>
  );
}
