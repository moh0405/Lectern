"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

/**
 * A query parameter's value when the component first rendered (trimmed, at most `max` characters), for
 * prefilling a field from a link such as `/compare?topic=heaps`. Later URL changes are ignored, so typing is
 * never overwritten. Needs a <Suspense> boundary above it.
 */
export function useInitialParam(key: string, max = 2000): string {
  const params = useSearchParams();
  const [value] = useState(() => (params.get(key) ?? "").trim().slice(0, max));
  return value;
}

/**
 * Read and update URL query parameters without adding history entries, so filters and
 * selections are shareable and survive a reload. Needs a <Suspense> boundary above it.
 */
export function useUrlParams() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const get = useCallback((key: string) => params.get(key) ?? "", [params]);
  const getList = useCallback((key: string) => (params.get(key) ?? "").split(",").filter(Boolean), [params]);

  const set = useCallback(
    (patch: Record<string, string | string[] | null>) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(patch)) {
        const v = Array.isArray(value) ? value.join(",") : value;
        if (v === null || v === "") next.delete(key);
        else next.set(key, v);
      }
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return { get, getList, set };
}
