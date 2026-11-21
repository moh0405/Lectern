"use client";

import { useMutation } from "@tanstack/react-query";
import { Link2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import styles from "./sources.module.css";

export function isWebLink(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === "http:" || url.protocol === "https:") && url.hostname.includes(".");
  } catch {
    return false;
  }
}

export interface UrlCheck {
  /** Valid, de-duplicated links in the order typed. */
  urls: string[];
  /** Lines that are not a web link (1-based line numbers). */
  invalid: { line: number; text: string }[];
}

/** One link per line; each line must be a full http(s) address. */
export function checkUrls(text: string): UrlCheck {
  const urls: string[] = [];
  const invalid: UrlCheck["invalid"] = [];
  text.split(/\r?\n/).forEach((raw, index) => {
    const line = raw.trim();
    if (!line) return;
    if (isWebLink(line)) {
      if (!urls.includes(line)) urls.push(line);
    } else invalid.push({ line: index + 1, text: line });
  });
  return { urls, invalid };
}

export function UrlCard({ onJob }: { onJob: (jobId: string, label: string) => void }) {
  const [text, setText] = useState("");
  const [touched, setTouched] = useState(false);
  const helpId = useId();
  const errorId = useId();
  const { urls, invalid } = checkUrls(text);
  // While typing the last line, wait until the field is left (or a new line is started) before calling it invalid.
  const lastLine = text.split(/\r?\n/).length;
  const shown = invalid.filter((entry) => touched || entry.line < lastLine);
  const valid = urls.length > 0 && invalid.length === 0;

  const add = useMutation({
    mutationFn: async (list: string[]) => unwrap(await api.http.POST("/api/v1/sources/urls", { body: { urls: list } })),
    onSuccess: (res) => {
      if (res.job_id) onJob(res.job_id, res.urls.length === 1 ? res.urls[0]! : `${res.urls.length} links`);
      setText("");
      setTouched(false);
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (valid && !add.isPending) add.mutate(urls);
  };

  return (
    <Card>
      <div className={styles.sectionHead}><div><div className={styles.titleRow}><CardTitle>Add links</CardTitle><span className={styles.scope}>Server index</span></div><p className="text-muted">Bring an article, repository, or captioned video into your library.</p></div></div>
      <form onSubmit={onSubmit} className="space-y-3" noValidate>
        <Textarea
          aria-label="URLs"
          aria-describedby={shown.length ? `${errorId} ${helpId}` : helpId}
          aria-invalid={shown.length ? true : undefined}
          disabled={add.isPending}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => setTouched(true)}
          placeholder={"https://www.youtube.com/watch?v=…\nhttps://github.com/owner/repo\nhttps://example.com/article"}
          rows={4}
        />
        <p id={helpId} className="text-xs leading-relaxed text-muted">YouTube videos (with captions), GitHub repositories (README and docs) and web articles. One full link per line, starting with https://.</p>
        {shown.length ? (
          <div id={errorId} className="text-sm text-bad" role="alert">
            <p>{shown.length === 1 ? "This line is not a web link:" : "These lines are not web links:"}</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              {shown.map((entry) => <li key={entry.line} className="[overflow-wrap:anywhere]">Line {entry.line}: “{entry.text}”</li>)}
            </ul>
          </div>
        ) : null}
        <Button type="submit" disabled={add.isPending || !valid}>
          {add.isPending ? <Spinner /> : <Link2 className="h-4 w-4" aria-hidden="true" />}
          Add {urls.length > 1 ? `${urls.length} links` : "link"}
        </Button>
        {add.isError ? <ErrorNotice>{errorMessage(add.error)}. Your links are still here; check them and try again.</ErrorNotice> : null}
      </form>
    </Card>
  );
}
