import type { APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

export const API = "http://127.0.0.1:8100";
const fixture = (name: string) => path.join(import.meta.dirname, "fixtures", name);

/** Index a fixture PDF (default: heaps.pdf) through the real API and wait for the job to finish. */
export async function indexFixture(request: APIRequestContext, name = "heaps.pdf") {
  const res = await request.post(`${API}/api/v1/sources/files`, {
    multipart: { files: { name, mimeType: "application/pdf", buffer: fs.readFileSync(fixture(name)) } },
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

export async function removeFixture(request: APIRequestContext, name = "heaps.pdf") {
  await request.delete(`${API}/api/v1/sources`, { params: { key: name } });
}
