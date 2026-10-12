import type { Metadata } from "next";
import { AskView } from "@/features/ask/ask-view";

export const metadata: Metadata = { title: "Ask" };

export default function Page() {
  return <AskView />;
}
