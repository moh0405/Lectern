import type { Metadata } from "next";
import { VisualizeView } from "@/features/visualize/visualize-view";

export const metadata: Metadata = { title: "Map" };

export default function Page() {
  return <VisualizeView />;
}
