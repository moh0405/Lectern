import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Tutor tools" };

export default function Page() {
  return <PageHeader title="Tutor tools" description="Coming up in this phase." />;
}
