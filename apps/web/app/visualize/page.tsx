import type { Metadata } from "next";
import { VisualizeView } from "@/features/visualize/visualize-view";

export const metadata: Metadata = { title: "Embedding map" };

export default function Page() {
  return <VisualizeView />;
}
