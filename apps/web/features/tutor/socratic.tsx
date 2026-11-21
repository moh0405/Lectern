"use client";

import { BookOpen, Compass, Lightbulb, MessagesSquare } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { FallbackNotice, LlmError } from "@/components/llm-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Textarea } from "@/components/ui/field";
import { api, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import { IdlePreview } from "./library";
import { PassageList } from "./passages";
import { Announce, BusyIcon, PendingPanel, useToolRequest } from "./pending";

export function Socratic() {
  const [question, setQuestion] = useState("");
  const [depth, setDepth] = useState(0);
  const [shown, setShown] = useState(0);
  const input = useRef<HTMLTextAreaElement>(null);

  const { run, cancel, cancelled, error } = useToolRequest(
    async (vars: { q: string; depth: number }, signal: AbortSignal) =>
      unwrap(await api.http.POST("/api/v1/socratic", { body: { question: vars.q, depth: vars.depth }, signal })),
    { onMutate: () => setShown(0) },
  );

  const start = (e: FormEvent) => {
    e.preventDefault();
    if (question.trim().length >= 3) {
      setDepth(0);
      run.mutate({ q: question.trim(), depth: 0 });
    }
  };
  const stillStuck = () => {
    const next = Math.min(depth + 1, 5);
    setDepth(next);
    run.mutate({ q: question.trim(), depth: next });
  };
  const hints = run.data?.hints ?? [];
  const chunks = run.data?.chunks ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={start} className="space-y-3">
          <div>
            <Label htmlFor="soc-q">What are you trying to work out?</Label>
            <Textarea ref={input} id="soc-q" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} maxLength={2000}
              placeholder="e.g. Why is binary search O(log n)?" />
          </div>
          <Button type="submit" disabled={run.isPending || question.trim().length < 3}>
            {run.isPending ? <BusyIcon /> : <MessagesSquare className="h-4 w-4" aria-hidden />}
            {run.isPending ? "Thinking…" : "Guide me"}
          </Button>
          <p className="text-xs text-muted">You get questions to think through and hints you reveal one at a time, never the answer.</p>
        </form>
      </Card>

      <PendingPanel running={run.isPending} label="Writing guiding questions…" onCancel={cancel} />
      <Announce>{cancelled ? "Cancelled." : run.data ? `${plural(run.data.questions.length, "question")} to think about.` : ""}</Announce>
      {!run.data && !run.isPending && !error ? (
        <IdlePreview
          items={["Three to five questions that lead you toward the answer.", "A ladder of hints, each more explicit, revealed only when you ask."]}
          pickLabel="Work on a topic from your library"
          onPick={(t) => {
            setQuestion(`How does ${t.toLowerCase()} work?`);
            input.current?.focus();
          }}
        />
      ) : null}
      {error ? <LlmError error={error} /> : null}
      <FallbackNotice warning={run.data?.warning} />

      {run.data ? (
        <div className="space-y-4" aria-busy={run.isPending}>
          <Card className="space-y-4">
            <p className="flex items-start gap-2 text-xs text-muted" data-testid="socratic-source">
              {chunks.length ? (
                <>
                  <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-2" aria-hidden />
                  Based on {plural(chunks.length, "passage")} from your material (listed below).
                </>
              ) : (
                <>
                  <Compass className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-2" aria-hidden />
                  General guidance (not taken from your material).
                </>
              )}
            </p>
            <div>
              <h2 className="mb-2 text-sm font-semibold text-muted">Think about</h2>
              <ol className="list-decimal space-y-1.5 pl-5">
                {run.data.questions.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ol>
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold text-muted">Hints</h2>
              {shown === 0 ? <p className="text-sm text-muted">Try the questions first. Reveal a hint only if you are stuck.</p> : null}
              <ul className="space-y-2" aria-live="polite">
                {hints.slice(0, shown).map((h, i) => (
                  <li key={i} className="flex gap-2 rounded-lg border border-border bg-bg/40 p-3 text-sm">
                    <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
                    <span>
                      <span className="mr-1 font-medium">Hint {i + 1}.</span>
                      {h}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex flex-wrap gap-2">
                {shown < hints.length ? (
                  <Button variant="secondary" size="sm" onClick={() => setShown((s) => s + 1)}>
                    Show hint {shown + 1} of {hints.length}
                  </Button>
                ) : hints.length ? (
                  <Button variant="secondary" size="sm" onClick={stillStuck} disabled={run.isPending || depth >= 5}>
                    Still stuck? Ask again with more help
                  </Button>
                ) : null}
              </div>
            </div>
          </Card>
          <PassageList chunks={chunks} prefix="socratic" query={question} title={`Based on ${plural(chunks.length, "passage")}`} />
        </div>
      ) : null}
    </div>
  );
}
