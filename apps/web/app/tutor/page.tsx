import type { Metadata } from "next";
import { Suspense } from "react";
import { TutorView } from "@/features/tutor/tutor-view";

export const metadata: Metadata = { title: "Tutor tools" };

export default function Page() {
  return (
    <Suspense>
      <TutorView />
    </Suspense>
  );
}
