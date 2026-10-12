import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Sources" };

export default function Page() {
  return <PageHeader title="Sources" description="Coming up in this phase." />;
}
