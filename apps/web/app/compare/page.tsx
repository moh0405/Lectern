import type { Metadata } from "next";
import { Synthesis, SynthesisFromUrl } from "@/features/tutor/synthesis";
import { ToolPage } from "@/features/tutor/tool-page";

export const metadata: Metadata = { title: "Compare sources" };

export default function Page() {
  return (
    <ToolPage eyebrow="Tools" title="Compare sources" description="See where your documents agree, where they differ, and one explanation that combines them." fallback={<Synthesis />}>
      <SynthesisFromUrl />
    </ToolPage>
  );
}
