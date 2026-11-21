"use client";

// Replaces the root layout when it fails, so it brings its own <html>, <body> and (inline) styles.
export default function GlobalError({ error, retry }: { error: unknown; retry: () => void }) {
  const digest = error instanceof Error && "digest" in error ? String((error as { digest?: unknown }).digest ?? "") : "";
  return (
    <html lang="en">
      <body style={{ background: "#10151b", color: "#e8edf3", fontFamily: "system-ui, sans-serif", display: "grid", placeItems: "center", minHeight: "100vh", margin: 0 }}>
        <title>Something went wrong · Lectern</title>
        <div role="alert" style={{ maxWidth: 440, textAlign: "center", padding: 24 }}>
          <h1 style={{ fontSize: 28, letterSpacing: "-0.03em", margin: "0 0 12px" }}>Lectern hit a problem</h1>
          <p style={{ color: "#a0acba", fontSize: 15, lineHeight: 1.6 }}>The app could not load. Try again in a moment; your sources and history are safe.</p>
          {digest ? <p style={{ fontFamily: "monospace", fontSize: 12, color: "#a0acba" }}>Error id: {digest}</p> : null}
          <button onClick={() => retry()} style={{ background: "#c0a7f4", color: "#251938", border: 0, borderRadius: 8, minHeight: 44, padding: "0 18px", fontSize: 15, fontWeight: 600, cursor: "pointer" }}>
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
