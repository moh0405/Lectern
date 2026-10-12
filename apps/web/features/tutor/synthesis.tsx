"use client";

import { useMutation } from "@tanstack/react-query";
import { GitCompare } from "lucide-react";
import { useState, type FormEvent } from "react";
import { FallbackNotice, LlmError } from "@/components/llm-error";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { Spinner } from "@/components/ui/feedback";
import { api, unwrap } from "@/lib/api";

function Bullets({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold text-muted">{title}</h2>
      {items.length ? (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {items.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">{empty}</p>
      )}
    </div>
  );
}

export function Synthesis() {
  const [topic, setTopic] = useState("");
  const run = useMutation({
    mutationFn: async (t: string) => unwrap(await api.http.POST("/api/v1/synthesis", { body: { topic: t } })),
  });
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (topic.trim().length >= 2) run.mutate(topic.trim());
  };
  const d = run.data;

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Label htmlFor="syn-topic">Topic to compare across your documents</Label>
            <Input id="syn-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Linked lists vs arrays" maxLength={200} />
          </div>
          <Button type="submit" disabled={run.isPending || topic.trim().length < 2}>
            {run.isPending ? <Spinner /> : <GitCompare className="h-4 w-4" />}
            Compare
          </Button>
        </form>
      </Card>
      {run.isError ? <LlmError error={run.error} /> : null}
      <FallbackNotice warning={d?.warning} />
      {d ? (
        <Card className="space-y-5">
          <div className="grid gap-5 md:grid-cols-2">
            <Bullets title="Where the sources agree" items={d.similarities} empty="No clear agreement found." />
            <Bullets title="Where they differ" items={d.conflicts} empty="No conflicts found." />
          </div>
          <div>
            <h2 className="mb-2 text-sm font-semibold text-muted">Combined explanation</h2>
            <Markdown>{d.synthesis}</Markdown>
          </div>
          {d.citations.length ? (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-muted">Who said what</h2>
              <ul className="space-y-1 text-sm">
                {d.citations.map((c, i) => (
                  <li key={i}>
                    {c.doc ? <span className="font-mono text-xs text-accent-2">{c.doc}</span> : null} {c.point}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
