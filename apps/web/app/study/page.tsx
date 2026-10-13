import type { Metadata } from "next";
import { StudyView } from "@/features/study/study-view";

export const metadata: Metadata = { title: "Flashcards" };

export default function Page() {
  return <StudyView />;
}
