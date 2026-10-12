"use client";

import type { components } from "@ai-study-mentor/api-client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, unwrap } from "@/lib/api";

export type Job = components["schemas"]["Job"];

export const isFinished = (job?: Job) => job?.status === "done" || job?.status === "failed";

/** Poll a background job until it finishes, then refresh everything that depends on the index. */
export function useJob(jobId: string | null) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["job", jobId],
    enabled: jobId !== null,
    queryFn: async () => unwrap(await api.http.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: jobId! } } })),
    refetchInterval: (q) => (isFinished(q.state.data) ? false : 800),
    retry: false,
  });
  const finished = isFinished(query.data);
  useEffect(() => {
    if (finished) {
      for (const key of ["documents", "stats", "health", "suggestions"]) void qc.invalidateQueries({ queryKey: [key] });
    }
  }, [finished, qc]);
  return query;
}
