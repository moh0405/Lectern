import type { Metadata } from "next";
import { SynthesisFromUrl } from "@/features/tutor/synthesis";
import { ToolPage } from "@/features/tutor/tool-page";

export const metadata: Metadata = { title: "Compare sources" };

export default function Page() {
  return (
    <ToolPage title="Compare sources" description="See where your documents agree, where they differ, and one explanation that combines them.">
      <SynthesisFromUrl />
    </ToolPage>
  );
}
