"use client";

import { Upload } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { errorMessage } from "@/lib/api";
import { uploadFiles } from "@/lib/upload";
import { cn } from "@/lib/utils";
import styles from "./sources.module.css";

const ACCEPT = ".pdf,.mp3,.mp4,.wav,.m4a";

export function UploadCard({ onJob }: { onJob: (jobId: string, label: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [over, setOver] = useState(false);
  const [rejected, setRejected] = useState<{ filename: string; error?: string | null }[]>([]);
  const upload = useMutation({
    mutationFn: uploadFiles,
    onSuccess: (result, files) => {
      setRejected(result.files.filter((file) => !file.ok));
      if (result.job_id) onJob(result.job_id, files.length === 1 ? files[0]!.name : `${files.length} files`);
    },
  });
  const submit = (list: FileList | File[] | null) => {
    const files = Array.from(list ?? []);
    if (!files.length || submitting.current) return;
    submitting.current = true;
    setRejected([]);
    void upload.mutateAsync(files).catch(() => { /* Mutation exposes the error below. */ }).finally(() => { submitting.current = false; });
  };
  const onDrop = (event: DragEvent) => { event.preventDefault(); setOver(false); submit(event.dataTransfer.files); };

  return (
    <Card>
      <div className={styles.sectionHead}><div><div className={styles.titleRow}><CardTitle>Upload files</CardTitle><span className={styles.scope}>Server index</span></div><p className="text-muted">Add PDFs or recordings to the source library. Accepted files are indexed in the background.</p></div></div>
      <div onDragOver={(event) => { event.preventDefault(); if (!submitting.current) setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop} className={cn(styles.dropzone, over && styles.dropOver)}>
        <span className={styles.dropIcon}>{upload.isPending ? <Spinner className="h-5 w-5" /> : <Upload className="h-5 w-5" aria-hidden="true" />}</span>
        <div className={styles.dropCopy}><p role="status">{upload.isPending ? "Uploading files…" : "Drop PDFs or recordings here"}</p><span>.pdf, .mp3, .mp4, .wav, .m4a · up to 50 MB each</span></div>
        <Button onClick={() => input.current?.click()} disabled={upload.isPending}>Choose files</Button>
        <input ref={input} type="file" multiple accept={ACCEPT} aria-label="Upload files" className="sr-only" disabled={upload.isPending} onChange={(event) => { submit(event.target.files); event.target.value = ""; }} />
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted">Audio processing needs an OpenAI key configured on the server. Only new or changed files are processed.</p>
      {upload.isSuccess && upload.data.job_id ? <p className="mt-3 text-sm text-muted" role="status">Upload received. Follow indexing progress in Processing activity below.</p> : null}
      {upload.isError ? <ErrorNotice className="mt-3">{errorMessage(upload.error)}. Choose the files again to retry.</ErrorNotice> : null}
      {rejected.map((file, index) => <ErrorNotice key={`${file.filename}-${index}`} className="mt-3"><span className="font-medium">{file.filename}:</span> {file.error || "This file was not accepted."} Check the file type and size before retrying.</ErrorNotice>)}
    </Card>
  );
}
