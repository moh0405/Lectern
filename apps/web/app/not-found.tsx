import Link from "next/link";
import { Card } from "@/components/ui/card";

export default function NotFound() {
  return (
    <Card className="mx-auto mt-10 max-w-lg space-y-3 text-center">
      <h1 className="text-lg font-semibold">Page not found</h1>
      <p className="text-sm text-muted">That address does not exist.</p>
      <Link href="/ask" className="inline-block rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/85">
        Go to Ask
      </Link>
    </Card>
  );
}
