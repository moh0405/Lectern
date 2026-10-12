import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Analytics" };

export default function Page() {
  return <PageHeader title="Analytics" description="Coming up in this phase." />;
}
