import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Math" };

export default function Page() {
  return <PageHeader title="Math" description="Coming up in this phase." />;
}
