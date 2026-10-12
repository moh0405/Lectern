"use client";

import { Upload } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { errorMessage } from "@/lib/api";
import { uploadFiles } from "@/lib/upload";
import { cn } from "@/lib/utils";

const ACCEPT = ".pdf,.mp3,.mp4,.wav,.m4a";

export function UploadCard({ onJob }: { onJob: (jobId: string, label: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [rejected, setRejected] = useState<{ filename: string; error?: string | null }[]>([]);

  const upload = useMutation({
    mutationFn: uploadFiles,
    onSuccess: (res, files) => {
      setRejected(res.files.filter((f) => !f.ok));
      if (res.job_id) onJob(res.job_id, files.length === 1 ? files[0]!.name : `${files.length} files`);
    },
  });

  const submit = (list: FileList | File[] | null) => {
    const files = Array.from(list ?? []);
    if (files.length) upload.mutate(files);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    submit(e.dataTransfer.files);
  };

  return (
    <Card>
      <CardTitle className="mb-3">Upload files</CardTitle>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-center transition-colors",
          over ? "border-accent bg-accent/10" : "border-border",
        )}
      >
        {upload.isPending ? <Spinner className="h-6 w-6" /> : <Upload className="h-6 w-6 text-muted" />}
        <p className="text-sm">Drop PDFs or audio here, or</p>
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={upload.isPending}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/85 disabled:opacity-50"
        >
          Choose files
        </button>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          aria-label="Upload files"
          className="sr-only"
          onChange={(e) => {
            submit(e.target.files);
            e.target.value = "";
          }}
        />
        <p className="text-xs text-muted">.pdf, .mp3, .mp4, .wav, .m4a · up to 50 MB each · audio needs an OpenAI key on the server</p>
      </div>
      {upload.isError ? <ErrorNotice className="mt-3">{errorMessage(upload.error)}</ErrorNotice> : null}
      {rejected.map((f) => (
        <ErrorNotice key={f.filename} className="mt-3">
          <span className="font-medium">{f.filename}:</span> {f.error}
        </ErrorNotice>
      ))}
    </Card>
  );
}
