"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <Card className="mx-auto mt-10 max-w-lg space-y-3 text-center" role="alert">
      <h1 className="text-lg font-semibold">Something went wrong</h1>
      <p className="text-sm text-muted">
        This page hit an unexpected error. Your sources and history are safe. You can try again, or switch to another page.
      </p>
      {error.digest ? <p className="font-mono text-xs text-muted">Error id: {error.digest}</p> : null}
      <Button onClick={() => retry()}>Try again</Button>
    </Card>
  );
}
