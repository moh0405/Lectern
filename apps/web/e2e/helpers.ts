import type { APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

export const API = "http://127.0.0.1:8100";
const PDF = path.join(import.meta.dirname, "fixtures", "heaps.pdf");

/** Index the fixture PDF through the real API and wait for the job to finish. */
export async function indexFixture(request: APIRequestContext) {
  const res = await request.post(`${API}/api/v1/sources/files`, {
    multipart: { files: { name: "heaps.pdf", mimeType: "application/pdf", buffer: fs.readFileSync(PDF) } },
  });
  const { job_id } = await res.json();
  for (let i = 0; i < 100; i++) {
    const job = await (await request.get(`${API}/api/v1/jobs/${job_id}`)).json();
    if (job.status === "done") return;
    if (job.status === "failed") throw new Error(`indexing failed: ${job.error}`);
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("indexing did not finish");
}

export async function removeFixture(request: APIRequestContext) {
  await request.delete(`${API}/api/v1/sources`, { params: { key: "heaps.pdf" } });
}
