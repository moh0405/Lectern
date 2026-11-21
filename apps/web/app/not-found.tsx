import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { SectionLinks, StatusPageHint } from "@/components/status-page";
import Link from "next/link";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <div className="status-page">
      <PageHeader
        eyebrow="404"
        title="Page not found"
        description="That address doesn't match any page in Lectern. It may have moved, or the link may have a typo."
      />
      <div className="status-page-actions">
        <Link href="/ask" className="status-page-button primary">Go to Ask</Link>
      </div>
      <SectionLinks />
      <StatusPageHint />
    </div>
  );
}
