"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { DemoContext } from "@/lib/demo";

export function Providers({ children, demo = false }: { children: ReactNode; demo?: boolean }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            refetchOnWindowFocus: false,
            // Client errors will not fix themselves; only retry network/5xx failures.
            retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
          },
        },
      }),
  );
  return (
    <DemoContext.Provider value={demo}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </DemoContext.Provider>
  );
}
