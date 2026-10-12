"use client";

// Replaces the root layout when it fails, so it brings its own <html>, <body> and (inline) styles.
export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <html lang="en">
      <body style={{ background: "#0a0e1a", color: "#e6e9f2", fontFamily: "system-ui, sans-serif", display: "grid", placeItems: "center", minHeight: "100vh", margin: 0 }}>
        <div role="alert" style={{ maxWidth: 420, textAlign: "center", padding: 24 }}>
          <h1 style={{ fontSize: 20 }}>AI Study Mentor hit a problem</h1>
          <p style={{ color: "#95a0bd", fontSize: 14 }}>The app could not load. Try again; if it keeps happening, check that the API is running.</p>
          {error.digest ? <p style={{ fontFamily: "monospace", fontSize: 12, color: "#95a0bd" }}>Error id: {error.digest}</p> : null}
          <button onClick={() => retry()} style={{ background: "#7c6cf0", color: "white", border: 0, borderRadius: 8, padding: "10px 16px", cursor: "pointer" }}>
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
