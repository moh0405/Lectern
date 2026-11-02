"use client";

import { Bot, CheckCircle2, Square, Wrench, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Markdown } from "@/components/markdown";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/field";
import { Badge, ErrorNotice, Notice, Spinner } from "@/components/ui/feedback";
import { pageLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TraceItem } from "./trace";
import { useAgentRun } from "./use-agent-run";

const EXAMPLES = [
  "Explain how hash tables handle collisions, using my material.",
  "Integrate x^2 + 3x, then find an Easy LeetCode problem that uses a hash table.",
  "Which of my documents covers graph traversal, and what do they say about BFS?",
];

const compact = (args: Record<string, unknown>) => {
  const text = JSON.stringify(args);
  return text.length > 140 ? `${text.slice(0, 137)}…` : text;
};

function Step({ item }: { item: TraceItem }) {
  if (item.kind === "thought") return <li className="text-sm italic text-muted">{item.text}</li>;
  return (
    <li className="space-y-1 rounded-lg border border-border bg-bg/40 p-2.5 text-sm" data-testid="tool-step">
      <div className="flex flex-wrap items-center gap-2">
        <Wrench className="h-3.5 w-3.5 text-muted" aria-hidden />
        <Badge className="font-mono">{item.name}</Badge>
        <code className="min-w-0 break-all text-xs text-muted">{compact(item.arguments)}</code>
      </div>
      <p className={cn("flex items-center gap-1.5 text-xs", item.status === "failed" ? "text-bad" : "text-muted")}>
        {item.status === "running" ? <Spinner className="h-3 w-3" /> : item.status === "failed" ? <XCircle className="h-3.5 w-3.5" aria-label="Failed" /> : <CheckCircle2 className="h-3.5 w-3.5 text-good" aria-label="Done" />}
        {item.status === "running" ? "running…" : item.summary}
      </p>
    </li>
  );
}

export function AgentView() {
  const { state, run, stop } = useAgentRun();
  const [task, setTask] = useState("");
  const [maxSteps, setMaxSteps] = useState(6);
  const running = state.status === "running";

  const submit = (text: string) => {
    const t = text.trim();
    if (t.length >= 3 && !running) void run(t, maxSteps);
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(task);
  };
  const bad = (state.done?.citations ?? []).filter((c) => c.status !== "ok");

  return (
    <>
      <PageHeader
        title="Agent"
        description="Give it a task. The model decides which tools to use (search your material, read a page, solve math, find a practice problem), and you can watch each call. It stops after a fixed number of steps."
      />

      <Card className="mb-6">
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor="task">Task</Label>
            <Textarea id="task" value={task} onChange={(e) => setTask(e.target.value)} rows={3} maxLength={2000} placeholder="e.g. Compare how my notes explain BFS and DFS, then find a medium graph problem to practise." />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                disabled={running}
                onClick={() => {
                  setTask(ex);
                  submit(ex);
                }}
                className="rounded-full border border-border bg-surface-2 px-3 py-1 text-xs text-muted transition-colors hover:border-accent hover:text-fg disabled:opacity-50"
              >
                {ex}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label htmlFor="steps">Most steps</Label>
              <Select id="steps" value={maxSteps} onChange={(e) => setMaxSteps(Number(e.target.value))} className="w-28">
                {[3, 4, 5, 6, 7, 8].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </div>
            {running ? (
              <Button type="button" variant="secondary" onClick={stop}>
                <Square className="h-3.5 w-3.5" /> Stop
              </Button>
            ) : (
              <Button type="submit" disabled={task.trim().length < 3}>
                <Bot className="h-4 w-4" /> Run agent
              </Button>
            )}
            <p className="text-xs text-muted">Each step is a model call; it counts against the daily limit.</p>
          </div>
        </form>
      </Card>

      {state.status !== "idle" ? (
        <div className="space-y-4" aria-busy={running}>
          <Card className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold leading-snug">{state.task}</h2>
              {state.status === "stopped" ? <Badge>stopped</Badge> : null}
            </div>

            <section aria-label="What the agent did">
              <h3 className="mb-2 text-sm font-semibold text-muted">What it did</h3>
              {state.trace.length ? (
                <ol className="space-y-2">
                  {state.trace.map((item, i) => (
                    <Step key={i} item={item} />
                  ))}
                </ol>
              ) : (
                <p className="flex items-center gap-2 text-sm text-muted">{running ? <><Spinner className="h-3.5 w-3.5" /> Thinking…</> : state.status === "done" ? "It answered without using any tools." : null}</p>
              )}
            </section>

            {state.error ? <ErrorNotice>{state.error.message}</ErrorNotice> : null}

            {state.answer ? (
              <section aria-label="Answer" aria-live="polite">
                <h3 className="mb-2 text-sm font-semibold text-muted">Answer</h3>
                <Markdown>{state.answer}</Markdown>
              </section>
            ) : null}

            {bad.length > 0 ? (
              <Notice>
                <p className="font-medium">This answer cites {bad.length === 1 ? "something" : "things"} the tools never returned. Check before relying on it.</p>
                <ul className="mt-1 list-disc pl-5">
                  {bad.map((c) => (
                    <li key={c.label} className="font-mono text-xs">[{c.label}]</li>
                  ))}
                </ul>
              </Notice>
            ) : null}
            {state.done?.wrapped_up ? <Notice>It reached the step limit, so the answer was written from what it had found so far.</Notice> : null}

            {state.chunks.length > 0 ? (
              <details>
                <summary className="cursor-pointer select-none text-sm text-muted hover:text-fg">Passages the tools returned ({state.chunks.length})</summary>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {state.chunks.map((c, i) => (
                    <Badge key={i} className="font-mono">
                      {c.doc}
                      {c.page ? ` · ${pageLabel(c.page, c.end_page, true)}` : ""}
                    </Badge>
                  ))}
                </div>
              </details>
            ) : null}

            {state.done ? (
              <p className="text-xs text-muted" data-testid="run-cost">
                {state.done.tool_calls} tool {state.done.tool_calls === 1 ? "call" : "calls"} · {state.done.llm_calls} model {state.done.llm_calls === 1 ? "call" : "calls"}
                {state.done.model ? ` · ${state.done.model}` : ""}
              </p>
            ) : null}
          </Card>
        </div>
      ) : null}
    </>
  );
}
