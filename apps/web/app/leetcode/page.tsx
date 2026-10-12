import type { Metadata } from "next";
import { Suspense } from "react";
import { LeetCodeView } from "@/features/leetcode/leetcode-view";

export const metadata: Metadata = { title: "LeetCode" };

export default function Page() {
  // useSearchParams (URL-backed filters) needs a Suspense boundary.
  return (
    <Suspense>
      <LeetCodeView />
    </Suspense>
  );
}
