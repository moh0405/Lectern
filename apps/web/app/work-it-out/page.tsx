import type { Metadata } from "next";
import { SocraticFromUrl } from "@/features/tutor/socratic";
import { ToolPage } from "@/features/tutor/tool-page";

export const metadata: Metadata = { title: "Work it out" };

export default function Page() {
  return (
    <ToolPage title="Work it out" description="Reason it through yourself, with guiding questions and hints instead of the answer.">
      <SocraticFromUrl />
    </ToolPage>
  );
}
