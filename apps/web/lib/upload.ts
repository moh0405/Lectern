import { api, unwrap } from "@/lib/api";

/** Upload files as multipart form data. Returns the accepted/rejected files and the background job id. */
export async function uploadFiles(files: File[]) {
  const result = await api.http.POST("/api/v1/sources/files", {
    // The generated type models the binary field as string[]; the serializer sends the real files.
    body: { files: [] as unknown as string[] },
    bodySerializer: () => {
      const form = new FormData();
      for (const f of files) form.append("files", f, f.name);
      return form;
    },
  });
  return unwrap(result);
}
