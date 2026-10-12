import { ApiError, errorMessage } from "@/lib/api";
import { ErrorNotice, Notice } from "@/components/ui/feedback";

/** Error display for anything that calls the language model: a missing key is explained, not alarming. */
export function LlmError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.code === "llm_unavailable") {
    return (
      <Notice>
        The server has no <code>GEMINI_API_KEY</code>, so the model cannot be used. Set it in <code>.env</code> and restart the API.
      </Notice>
    );
  }
  return <ErrorNotice>{errorMessage(error)}</ErrorNotice>;
}

/** Shown when the API answered with a built-in offline fallback instead of the model. */
export function FallbackNotice({ warning }: { warning?: string | null }) {
  if (!warning) return null;
  return (
    <Notice>
      This is a basic offline fallback, not a model answer. Reason: <span className="font-mono text-xs">{warning}</span>
    </Notice>
  );
}
