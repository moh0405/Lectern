import type { Metadata } from "next";
import { Adaptive, AdaptiveFromUrl } from "@/features/tutor/adaptive";
import { ToolPage } from "@/features/tutor/tool-page";

export const metadata: Metadata = { title: "Explain at my level" };

export default function Page() {
  return (
    <ToolPage title="Explain at my level" description="The same idea explained your way, from ELI5 to expert, using your material." fallback={<Adaptive />}>
      <AdaptiveFromUrl />
    </ToolPage>
  );
}
