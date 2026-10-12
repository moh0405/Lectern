import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Ask" };

export default function Page() {
  return <PageHeader title="Ask" description="Coming up in this phase." />;
}
