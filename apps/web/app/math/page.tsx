import type { Metadata } from "next";
import { MathView } from "@/features/math/math-view";

export const metadata: Metadata = { title: "Math" };

export default function Page() {
  return <MathView />;
}
