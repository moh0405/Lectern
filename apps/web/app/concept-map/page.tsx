import type { Metadata } from "next";
import { ConceptMapFromUrl } from "@/features/tutor/concept-map";
import { ToolPage } from "@/features/tutor/tool-page";

export const metadata: Metadata = { title: "Concept map" };

export default function Page() {
  return (
    <ToolPage title="Concept map" description="See how the ideas in a topic connect, drawn from your sources.">
      <ConceptMapFromUrl />
    </ToolPage>
  );
}
