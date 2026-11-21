"use client";

import { RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorNotice } from "@/components/ui/feedback";
import { errorMessage } from "@/lib/api";

/**
 * A failed load, said once, with a way to try again. `what` names the thing that did not load
 * ("your flashcards", "the study plan"), so the message reads as a sentence for students.
 */
export function QueryError({ error, what, onRetry, retrying = false, className }: {
  error: unknown;
  what: string;
  onRetry: () => void;
  retrying?: boolean;
  className?: string;
}) {
  return (
    <ErrorNotice className={className}>
      <p>Could not load {what}. {errorMessage(error)}</p>
      <Button variant="secondary" size="sm" className="mt-2" disabled={retrying} onClick={onRetry}>
        <RotateCw className="h-4 w-4" aria-hidden="true" />
        {retrying ? "Retrying…" : "Retry"}
      </Button>
    </ErrorNotice>
  );
}
