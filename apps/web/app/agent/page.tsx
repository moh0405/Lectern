import type { Metadata } from "next";
import { AgentView } from "@/features/agent/agent-view";

export const metadata: Metadata = { title: "Agent" };

export default function Page() {
  return <AgentView />;
}
