"use client";

import { Bot, CheckCircle2, Square, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Markdown } from "@/components/markdown";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/field";
import { Badge, ErrorNotice, Notice } from "@/components/ui/feedback";
import { useDemo } from "@/lib/demo";
import { cn } from "@/lib/utils";
import { chipClass, LibraryLine, useLibrary } from "@/features/tutor/library";
import { PassageList } from "@/features/tutor/passages";
import { Announce, BusyIcon, useElapsed, useFocusAfterRender } from "@/features/tutor/pending";
import { modelsLabel, stepLabel, type TraceItem } from "./trace";
import { useAgentRun } from "./use-agent-run";

const EXAMPLES = [
  "Explain how hash tables handle collisions, using my material.",
  "Integrate x^2 + 3x, then find an Easy LeetCode problem that uses a hash table.",
  "Which of my documents covers graph traversal, and what do they say about BFS?",
];

function Step({ item, n }: { item: Extract<TraceItem, { kind: "tool" }>; n: number }) {
  const args = Object.keys(item.arguments ?? {}).length ? JSON.stringify(item.arguments, null, 2) : null;
  return (
    <li className="flex gap-3 rounded-lg border border-border bg-bg/40 p-2.5 text-sm" data-testid="tool-step">
      <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full border border-border font-mono text-xs text-muted" aria-hidden>
        {n}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-medium">
          <span className="sr-only">Step {n}: </span>
          {stepLabel(item.name, item.arguments, item.status === "running")}
        </p>
        <p className={cn("flex items-center gap-1.5 text-xs", item.status === "failed" ? "text-bad" : "text-muted")}>
          {item.status === "running" ? (
            <BusyIcon className="h-3 w-3" />
          ) : item.status === "failed" ? (
            <XCircle className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5 text-good" aria-hidden />
          )}
          <span className="sr-only">{item.status === "failed" ? "Failed: " : item.status === "ok" ? "Done: " : ""}</span>
          {item.status === "running" ? "running…" : item.summary}
        </p>
        <details className="text-xs text-muted">
          <summary className="inline-flex min-h-8 cursor-pointer select-none items-center hover:text-fg pointer-coarse:min-h-11">Details</summary>
          <p className="mt-1">
            Tool <code className="font-mono text-fg">{item.name}</code>
          </p>
          {args ? <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all rounded bg-bg/60 p-2 font-mono">{args}</pre> : null}
        </details>
      </div>
    </li>
  );
}

function Trace({ items }: { items: TraceItem[] }) {
  let n = 0;
  return (
    <ol className="space-y-2">
      {items.map((item, i) =>
        item.kind === "thought" ? (
          <li key={i} className="pl-9 text-sm italic text-muted">
            {item.text}
          </li>
        ) : (
          <Step key={i} item={item} n={++n} />
        ),
      )}
    </ol>
  );
}

export function AgentView() {
  const { state, run, stop } = useAgentRun();
  const [task, setTask] = useState("");
  const [maxSteps, setMaxSteps] = useState(6);
  const running = state.status === "running";
  const seconds = useElapsed(running);
  const demo = useDemo();
  const lib = useLibrary();
  const focusAfterRender = useFocusAfterRender();

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
        eyebrow="Tools"
        title="Agent"
        description="Hand it a multi-step task and watch which tools it uses to answer from your material."
      />

      <Card className="mb-6">
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor="task">Task</Label>
            <Textarea id="task" value={task} onChange={(e) => setTask(e.target.value)} rows={3} maxLength={2000} placeholder="e.g. Compare how my notes explain BFS and DFS, then find a medium graph problem to practise." />
          </div>
          <div role="group" aria-labelledby="agent-examples">
            <p id="agent-examples" className="mb-1.5 text-xs text-muted">
              Use an example (fills the box above; nothing runs until you press Run agent)
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  disabled={running}
                  aria-label={`Use example: ${ex}`}
                  onClick={() => {
                    setTask(ex);
                    focusAfterRender("agent-run"); // once it is enabled
                  }}
                  className={chipClass}
                >
                  {ex}
                </button>
              ))}
            </div>
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
                <Square className="h-3.5 w-3.5" aria-hidden /> Stop
              </Button>
            ) : (
              <Button id="agent-run" type="submit" disabled={task.trim().length < 3}>
                <Bot className="h-4 w-4" aria-hidden /> Run agent
              </Button>
            )}
            <p className="text-xs text-muted">Each step is a model call; it counts against the daily limit.</p>
          </div>
          <LibraryLine names={lib.names} pending={lib.isPending} demo={demo} />
          {demo ? <p className="text-xs text-muted" data-testid="demo-scope">Your browser documents are used on Ask, not here.</p> : null}
        </form>
      </Card>

      {state.status !== "idle" ? (
        <div className="space-y-4" aria-busy={running}>
          <Card className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold leading-snug">{state.task}</h2>
              {state.status === "stopped" ? <Badge>stopped</Badge> : running ? <span className="shrink-0 text-xs tabular-nums text-muted" aria-hidden>{seconds} s</span> : null}
            </div>

            <section aria-label="What the agent did">
              <h3 className="mb-2 text-sm font-semibold text-muted">What it did</h3>
              {state.trace.length ? <Trace items={state.trace} /> : (
                <p className="flex items-center gap-2 text-sm text-muted">{running ? <><BusyIcon className="h-3.5 w-3.5" /> Thinking…</> : state.status === "done" ? "It answered without using any tools." : null}</p>
              )}
            </section>

            {state.error ? <ErrorNotice>{state.error.message}</ErrorNotice> : null}

            {state.answer ? (
              <section aria-label="Answer">
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


            {state.done ? (
              <p className="text-xs text-muted" data-testid="run-cost">
                {state.done.tool_calls} tool {state.done.tool_calls === 1 ? "call" : "calls"} · {state.done.llm_calls} model {state.done.llm_calls === 1 ? "call" : "calls"}
                {modelsLabel(state.done) ? ` · ${modelsLabel(state.done)}` : ""}
              </p>
            ) : null}
          </Card>
          {state.chunks.length > 0 ? (
            <PassageList chunks={state.chunks} prefix="agent" query={state.task} title={`Passages the tools returned (${state.chunks.length})`} />
          ) : null}
          <Announce>{state.status === "done" ? "The agent finished." : state.status === "stopped" ? "Stopped." : ""}</Announce>
        </div>
      ) : null}
    </>
  );
}
