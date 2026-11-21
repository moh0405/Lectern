"use client";

import { Suspense, type ReactNode } from "react";
import { PageHeader } from "@/components/page-header";
import { useDemo } from "@/lib/demo";

/**
 * The frame every study tool page shares (Concept map, Compare sources, Work it out, Explain at my level):
 * its heading, the demo's note on which documents it reads, and the tool. The tool sits in a Suspense
 * boundary because it reads its prefill from the URL, which keeps the heading in the server-rendered HTML.
 */
export function ToolPage({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  const demo = useDemo();
  return (
    <>
      <PageHeader title={title} description={description} />
      {demo ? (
        <p className="-mt-2 mb-4 text-xs text-muted" data-testid="demo-scope">
          Uses the shared textbooks; your browser documents are used on Ask.
        </p>
      ) : null}
      <Suspense>{children}</Suspense>
    </>
  );
}
