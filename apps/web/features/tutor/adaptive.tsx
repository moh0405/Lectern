"use client";

import { useMutation } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ChunkCard } from "@/components/chunk-card";
import { FallbackNotice, LlmError } from "@/components/llm-error";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/field";
import { Badge, Spinner } from "@/components/ui/feedback";
import { api, unwrap } from "@/lib/api";

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
  const [level, setLevel] = useState<Level>("Undergrad");
  const run = useMutation({
    mutationFn: async (vars: { q: string; level: Level }) =>
      unwrap(await api.http.POST("/api/v1/adaptive", { body: { question: vars.q, level: vars.level } })),
  });
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (question.trim().length >= 3) run.mutate({ q: question.trim(), level });
  };
  const d = run.data;

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor="ad-q">Question</Label>
            <Textarea id="ad-q" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} maxLength={2000}
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
              {run.isPending ? <Spinner /> : <GraduationCap className="h-4 w-4" />}
              Explain
            </Button>
          </div>
        </form>
      </Card>
      {run.isError ? <LlmError error={run.error} /> : null}
      <FallbackNotice warning={d?.warning} />
      {d ? (
        <Card className="space-y-4">
          <div className="flex gap-1.5">
            <Badge>{d.level}</Badge>
            {d.model ? <Badge>{d.model}</Badge> : null}
          </div>
          <Markdown>{d.answer}</Markdown>
          {d.chunks.length ? (
            <details>
              <summary className="cursor-pointer text-sm text-muted hover:text-fg">Sources ({d.chunks.length})</summary>
              <div className="mt-3 grid gap-2">
                {d.chunks.map((c, i) => (
                  <ChunkCard key={i} chunk={c} query={question} index={i} />
                ))}
              </div>
            </details>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
