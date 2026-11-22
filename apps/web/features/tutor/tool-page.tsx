"use client";

import { Suspense, type ReactNode } from "react";
import { PageHeader } from "@/components/page-header";
import { useDemo } from "@/lib/demo";

/**
 * The frame every study tool page shares (Concept map, Compare sources, Work it out, Explain at my level):
 * its heading, the demo's note on which documents it reads, and the tool. The tool sits in a Suspense
 * boundary because it reads its prefill from the URL, which keeps the heading in the server-rendered HTML.
 * `fallback` is the same tool without a prefill: it is what the server renders (a URL-reading component
 * cannot be prerendered), so the form and its idle preview paint with the HTML instead of waiting for the
 * page's JavaScript (on a throttled phone that wait made the idle preview the late LCP element).
 */
export function ToolPage({ title, description, fallback, children }: { title: string; description: string; fallback?: ReactNode; children: ReactNode }) {
  const demo = useDemo();
  return (
    <>
      <PageHeader title={title} description={description} />
      {demo ? (
        <p className="-mt-2 mb-4 text-xs text-muted" data-testid="demo-scope">
          Uses the shared textbooks; your browser documents are used on Ask.
        </p>
      ) : null}
      <Suspense fallback={fallback}>{children}</Suspense>
    </>
  );
}
