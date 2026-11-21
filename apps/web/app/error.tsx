"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { PageHeader } from "@/components/page-header";
import { SectionLinks } from "@/components/status-page";

export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  const queryClient = useQueryClient();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    console.error(error);
  }, [error]);
  // Move focus here so keyboard and screen-reader users learn the page failed (and are not left on a removed element).
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, []);
  const digest = error instanceof globalThis.Error && "digest" in error ? String((error as { digest?: unknown }).digest ?? "") : "";

  // Data that made the page crash is still cached: drop it (except the shell's health check) so a retry fetches fresh data.
  const clearCache = () => queryClient.resetQueries({ predicate: (q) => q.queryKey[0] !== "health" });

  return (
    <div className="status-page">
      <PageHeader
        eyebrow="Error"
        title="Something went wrong"
        headingRef={heading}
        description="This page hit an unexpected error. Your sources and history are safe. Try again, or go to another page."
      />
      <div className="status-page-actions">
        <button
          type="button"
          className="status-page-button primary"
          onClick={() => {
            void clearCache();
            retry();
          }}
        >
          Try again
        </button>
        <Link href="/ask" className="status-page-button" onClick={() => void clearCache()}>Go to Ask</Link>
        <button type="button" className="status-page-button" onClick={() => window.location.reload()}>Reload page</button>
      </div>
      {digest ? <p className="status-page-hint font-mono">Error id: {digest}</p> : null}
      <SectionLinks />
    </div>
  );
}
