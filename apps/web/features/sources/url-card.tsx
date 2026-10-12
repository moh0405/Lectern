"use client";

import { useMutation } from "@tanstack/react-query";
import { Link2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";

export function parseUrls(text: string): string[] {
  return [...new Set(text.split(/[\s,]+/).map((u) => u.trim()).filter(Boolean))];
}

export function UrlCard({ onJob }: { onJob: (jobId: string, label: string) => void }) {
  const [text, setText] = useState("");
  const urls = parseUrls(text);

  const add = useMutation({
    mutationFn: async (list: string[]) => unwrap(await api.http.POST("/api/v1/sources/urls", { body: { urls: list } })),
    onSuccess: (res) => {
      if (res.job_id) onJob(res.job_id, res.urls.length === 1 ? res.urls[0]! : `${res.urls.length} URLs`);
      setText("");
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (urls.length) add.mutate(urls);
  };

  return (
    <Card>
      <CardTitle className="mb-3">Add links</CardTitle>
      <form onSubmit={onSubmit} className="space-y-3">
        <Textarea
          aria-label="URLs"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={"https://www.youtube.com/watch?v=…\nhttps://github.com/owner/repo\nhttps://example.com/article"}
          rows={4}
        />
        <p className="text-xs text-muted">YouTube videos (with captions), GitHub repositories (README and docs) and web articles. One per line.</p>
        <Button type="submit" disabled={add.isPending || urls.length === 0}>
          {add.isPending ? <Spinner /> : <Link2 className="h-4 w-4" />}
          Add {urls.length > 1 ? `${urls.length} links` : "link"}
        </Button>
        {add.isError ? <ErrorNotice>{errorMessage(add.error)}</ErrorNotice> : null}
      </form>
    </Card>
  );
}
