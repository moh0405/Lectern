import type { Metadata } from "next";
import { Suspense } from "react";
import { PageHeader } from "@/components/page-header";
import { LeetCodeView } from "@/features/leetcode/leetcode-view";

export const metadata: Metadata = { title: "LeetCode" };

export default function Page() {
  // useSearchParams (URL-backed filters) needs a Suspense boundary, and what is inside it is rendered only in
  // the browser. The heading stays outside it, so it paints with the HTML instead of after the JavaScript.
  return (
    <>
      <PageHeader
        eyebrow="Practice"
        title="LeetCode"
        description="Search a bank of coding problems and get an AI study guide for any of them."
      />
      {/* The fallback keeps the footer below the fold until the view renders, so it never jumps away. */}
      <Suspense fallback={<div className="min-h-dvh" aria-hidden="true" />}>
        <LeetCodeView />
      </Suspense>
    </>
  );
}
