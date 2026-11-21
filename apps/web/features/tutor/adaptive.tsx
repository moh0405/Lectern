"use client";

import { GraduationCap } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { FallbackNotice, LlmError } from "@/components/llm-error";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/field";
import { api, unwrap } from "@/lib/api";
import { IdlePreview } from "./library";
import { PassageList } from "./passages";
import { Announce, BusyIcon, PendingPanel, useToolRequest } from "./pending";

const LEVELS = [
  { value: "ELI5", label: "ELI5: like I'm five" },
  { value: "ELI10", label: "ELI10: middle school" },
  { value: "Undergrad", label: "Undergraduate" },
  { value: "Grad", label: "Graduate" },
  { value: "Expert", label: "Expert" },
] as const;
type Level = (typeof LEVELS)[number]["value"];

export function Adaptive() {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [level, setLevel] = useState<Level>("Undergrad");
  const input = useRef<HTMLTextAreaElement>(null);
  const { run, cancel, cancelled, error } = useToolRequest(
    async (vars: { q: string; level: Level }, signal: AbortSignal) =>
      unwrap(await api.http.POST("/api/v1/adaptive", { body: { question: vars.q, level: vars.level }, signal })),
  );
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (question.trim().length >= 3) {
      setAsked(question.trim());
      run.mutate({ q: question.trim(), level });
    }
  };
  const d = run.data;
  const levelLabel = (v: string) => LEVELS.find((l) => l.value === v)?.label ?? v;

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor="ad-q">Question</Label>
            <Textarea ref={input} id="ad-q" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} maxLength={2000}
              placeholder="e.g. Explain dynamic programming." />
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-48">
              <Label htmlFor="ad-level">Explain it at</Label>
              <Select id="ad-level" value={level} onChange={(e) => setLevel(e.target.value as Level)}>
                {LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit" disabled={run.isPending || question.trim().length < 3}>
              {run.isPending ? <BusyIcon /> : <GraduationCap className="h-4 w-4" aria-hidden />}
              {run.isPending ? "Explaining…" : "Explain"}
            </Button>
          </div>
        </form>
      </Card>
      <PendingPanel running={run.isPending} onCancel={cancel} />
      <Announce>{cancelled ? "Cancelled." : d ? "Explanation ready." : ""}</Announce>
      {!d && !run.isPending && !error ? (
        <IdlePreview
          items={["An explanation pitched at the level you choose, from ELI5 to expert.", "The passages from your material it drew on."]}
          pickLabel="Ask about a topic from your library"
          onPick={(t) => {
            setQuestion(`Explain ${t.toLowerCase()}.`);
            input.current?.focus();
          }}
        />
      ) : null}
      {error ? <LlmError error={error} /> : null}
      <FallbackNotice warning={d?.warning} />
      {d ? (
        <div className="space-y-4" aria-busy={run.isPending}>
          <Card className="space-y-3">
            <Markdown>{d.answer}</Markdown>
            <p className="border-t border-border pt-2 text-xs text-muted" data-testid="answer-meta">
              Explained at <span className="text-fg">{levelLabel(d.level)}</span>
              {d.model ? (
                <>
                  {" "}
                  · <span className="font-mono">{d.model}</span>
                </>
              ) : null}
            </p>
          </Card>
          <PassageList chunks={d.chunks} prefix="adaptive" query={asked} showRelevance />
        </div>
      ) : null}
    </div>
  );
}
