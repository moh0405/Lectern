"use client";

import { useQuery } from "@tanstack/react-query";
import { listDocs, type StoredDoc } from "./store";

export const LOCAL_DOCS_KEY = ["local-docs"] as const;

/** The visitor's own documents (empty while loading, or if browser storage is blocked). */
export function useLocalDocs() {
  return useQuery<StoredDoc[]>({
    queryKey: LOCAL_DOCS_KEY,
    queryFn: async () => {
      try {
        return await listDocs();
      } catch {
        return [];
      }
    },
    staleTime: Infinity,
  });
}
