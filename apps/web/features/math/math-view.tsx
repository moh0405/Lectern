"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Sigma, Trash2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/page-header";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { Badge, ErrorNotice } from "@/components/ui/feedback";
import { ApiError, api, errorMessage, unwrap } from "@/lib/api";
import { chipClass } from "@/features/tutor/library";
import { Announce, BusyIcon, useFocusAfterRender } from "@/features/tutor/pending";
import { cn } from "@/lib/utils";

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

/** Where in the input a math error points, from the API's `details.position` (0-based), if it gave one. */
export function errorPosition(err: unknown, text: string): number | null {
  if (!(err instanceof ApiError) || err.code !== "math_error") return null;
  const pos = (err.details as { position?: unknown } | undefined)?.position;
  return typeof pos === "number" && pos >= 0 && pos <= text.length ? pos : null;
}

/** The submitted text with the character at `pos` marked (a marked space when it points past the end). */
function Pointed({ text, pos }: { text: string; pos: number }) {
  return (
    <code className="mt-1 block overflow-x-auto whitespace-pre rounded bg-bg/60 px-2 py-1 font-mono text-sm text-fg" data-testid="math-error-at">
      {text.slice(0, pos)}
      <mark className="rounded-sm bg-bad/25 px-px text-fg underline decoration-bad decoration-2 underline-offset-4">{text[pos] ?? " "}</mark>
      {text.slice(pos + 1)}
    </code>
  );
}

export function MathView() {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<Entry[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const focusAfterRender = useFocusAfterRender();

  const run = useMutation({
    mutationFn: async (text: string) => ({ text, res: unwrap(await api.http.POST("/api/v1/math", { body: { input: text } })) }),
    onSuccess: ({ text, res }) => setHistory((h) => [{ input: text, ...res }, ...h].slice(0, 10)),
  });
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const t = input.trim();
    if (t) run.mutate(t);
  };
  const isUserError = run.error instanceof ApiError && run.error.code === "math_error";
  const submitted = run.variables ?? "";
  const pos = errorPosition(run.error, submitted);
  const showFieldError = run.isError && isUserError && submitted === input.trim();

  return (
    <>
      <PageHeader eyebrow="Tools" title="Math" description="Exact symbolic answers, typeset, for the algebra and calculus in your course." />
      <Card className="mb-4">
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor="math-in">Expression</Label>
            <div className="flex gap-2">
              <Input ref={inputRef} id="math-in" value={input} onChange={(e) => setInput(e.target.value)} maxLength={200} autoComplete="off" spellCheck={false}
                placeholder="differentiate sin(x)" className="font-mono"
                aria-invalid={showFieldError || undefined} aria-describedby={showFieldError ? "math-error" : "math-help"} />
              <Button id="math-compute" type="submit" disabled={run.isPending || !input.trim()}>
                {run.isPending ? <BusyIcon /> : <Sigma className="h-4 w-4" aria-hidden />}
                {run.isPending ? "Computing…" : "Compute"}
              </Button>
            </div>
            {showFieldError ? (
              <div id="math-error" role="alert" className="mt-2 text-sm text-bad">
                <p className="flex items-start gap-1.5">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  <span>
                    {run.error?.message}
                    {pos !== null ? <span className="sr-only">, at character {pos + 1}</span> : null}
                  </span>
                </p>
                {pos !== null ? <Pointed text={submitted} pos={pos} /> : null}
              </div>
            ) : null}
          </div>
          <div role="group" aria-labelledby="math-examples">
            <p id="math-examples" className="mb-1.5 text-xs text-muted">
              Use an example (fills the box; press Compute to run it)
            </p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => {
                    setInput(ex);
                    focusAfterRender("math-compute");
                  }}
                  className={cn(chipClass, "font-mono")}
                  aria-label={`Use example: ${ex}`}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
          <p id="math-help" className="text-xs text-muted">
            Commands: <code>differentiate</code>, <code>integrate</code>, <code>simplify</code>, <code>expand</code>, <code>factor</code>,{" "}
            <code>solve … for x</code>, or just an expression. Use <code>^</code> for powers; <code>x</code>, <code>pi</code>, <code>sin</code>,{" "}
            <code>log</code>, <code>sqrt</code> and friends are available.
          </p>
        </form>
      </Card>

      {run.isError && !isUserError ? <ErrorNotice className="mb-4">{errorMessage(run.error)}</ErrorNotice> : null}
      <Announce>{run.isSuccess && history[0] ? `Result ready for ${history[0].input}.` : ""}</Announce>

      {history.length ? (
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-muted">Results</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setHistory([]);
              inputRef.current?.focus();
            }}
          >
            <Trash2 className="h-4 w-4" aria-hidden /> Clear history
          </Button>
        </div>
      ) : null}
      <div className="space-y-3" aria-busy={run.isPending}>
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
