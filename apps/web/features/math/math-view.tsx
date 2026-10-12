"use client";

import { useMutation } from "@tanstack/react-query";
import { Sigma } from "lucide-react";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/page-header";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { Badge, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { ApiError, api, errorMessage, unwrap } from "@/lib/api";

const EXAMPLES = [
  "differentiate sin(x)*x^2",
  "integrate x^2 + 3x",
  "simplify (x^2 - 1)/(x - 1)",
  "solve x^2 - 5x + 6 = 0",
  "expand (x + 1)^4",
  "factor x^3 - x",
];

interface Entry {
  input: string;
  kind: string;
  latex: string;
  steps: string[];
}

export function MathView() {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<Entry[]>([]);

  const run = useMutation({
    mutationFn: async (text: string) => ({ text, res: unwrap(await api.http.POST("/api/v1/math", { body: { input: text } })) }),
    onSuccess: ({ text, res }) => setHistory((h) => [{ input: text, ...res }, ...h].slice(0, 10)),
  });
  const submit = (text: string) => {
    const t = text.trim();
    if (t) run.mutate(t);
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(input);
  };
  const isUserError = run.error instanceof ApiError && run.error.code === "math_error";

  return (
    <>
      <PageHeader
        title="Math"
        description="Differentiate, integrate, simplify, expand, factor or solve, with the result as typeset math."
      />
      <Card className="mb-4">
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor="math-in">Expression</Label>
            <div className="flex gap-2">
              <Input id="math-in" value={input} onChange={(e) => setInput(e.target.value)} maxLength={200} autoComplete="off" spellCheck={false}
                placeholder="differentiate sin(x)" className="font-mono" />
              <Button type="submit" disabled={run.isPending || !input.trim()}>
                {run.isPending ? <Spinner /> : <Sigma className="h-4 w-4" />}
                Compute
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  setInput(ex);
                  submit(ex);
                }}
                className="rounded-full border border-border bg-surface-2 px-3 py-1 font-mono text-xs text-muted transition-colors hover:border-accent hover:text-fg"
              >
                {ex}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted">
            Commands: <code>differentiate</code>, <code>integrate</code>, <code>simplify</code>, <code>expand</code>, <code>factor</code>,{" "}
            <code>solve … for x</code>, or just an expression. Use <code>^</code> for powers; <code>x</code>, <code>pi</code>, <code>sin</code>,{" "}
            <code>log</code>, <code>sqrt</code> and friends are available.
          </p>
        </form>
      </Card>

      {run.isError ? (
        <ErrorNotice className="mb-4">{isUserError ? run.error.message : errorMessage(run.error)}</ErrorNotice>
      ) : null}

      <div className="space-y-3">
        {history.map((h, i) => (
          <Card key={`${h.input}-${i}`} className="space-y-2" data-testid="math-result">
            <div className="flex items-center justify-between gap-2">
              <code className="min-w-0 truncate text-sm text-muted">{h.input}</code>
              <Badge>{h.kind}</Badge>
            </div>
            <Markdown className="py-1 text-lg">{`$$${h.latex}$$`}</Markdown>
            <ol className="list-decimal pl-5 text-xs text-muted">
              {h.steps.map((s, j) => (
                <li key={j}>{s}</li>
              ))}
            </ol>
          </Card>
        ))}
      </div>
    </>
  );
}
