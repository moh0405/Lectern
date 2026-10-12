import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "LeetCode" };

export default function Page() {
  return <PageHeader title="LeetCode" description="Coming up in this phase." />;
}
