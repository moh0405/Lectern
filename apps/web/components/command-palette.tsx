"use client";

import { Command } from "cmdk";
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { NAV } from "@/lib/nav";

interface Item {
  label: string;
  hint?: string;
  href: string;
  keywords?: string[];
}

const TOOLS: Item[] = [
  { label: "Concept map", hint: "Tutor tools", href: "/tutor", keywords: ["graph", "diagram", "topic"] },
  { label: "Socratic tutor", hint: "Tutor tools", href: "/tutor?tool=socratic", keywords: ["hints", "guide"] },
  { label: "Compare sources", hint: "Tutor tools", href: "/tutor?tool=synthesis", keywords: ["synthesis", "documents"] },
  { label: "Explain at my level", hint: "Tutor tools", href: "/tutor?tool=adaptive", keywords: ["eli5", "adaptive"] },
  { label: "Upload a PDF", hint: "Sources", href: "/sources", keywords: ["file", "audio", "add"] },
  { label: "Add a link", hint: "Sources", href: "/sources", keywords: ["youtube", "github", "url", "web"] },
  { label: "Hard tree problems", hint: "LeetCode", href: "/leetcode?d=Hard&t=Tree" },
  { label: "Easy array problems", hint: "LeetCode", href: "/leetcode?d=Easy&t=Array" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const row = "flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm aria-selected:bg-accent/25";
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="workspace-jump"
      >
        <Search className="h-3.5 w-3.5" />
        <span className="flex-1 text-left">Jump to…</span>
        <kbd className="rounded border border-border px-1.5 font-mono">⌘ / Ctrl K</kbd>
      </button>
      <Command.Dialog
        open={open}
        onOpenChange={setOpen}
        label="Command palette"
        overlayClassName="fixed inset-0 z-40 bg-black/60"
        contentClassName="fixed left-1/2 top-[18%] z-50 w-[min(92vw,34rem)] -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
      >
        <Command.Input
          autoFocus
          placeholder="Go to a page or tool…"
          className="w-full border-b border-border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted"
        />
        <Command.List className="max-h-80 overflow-y-auto p-2">
          <Command.Empty className="px-3 py-6 text-center text-sm text-muted">Nothing matches.</Command.Empty>
          <Command.Group heading="Pages" className="text-xs text-muted [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5">
            {NAV.map(({ href, label, icon: Icon }) => (
              <Command.Item key={href} value={`page ${label}`} onSelect={() => go(href)} className={row}>
                <span className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-muted" />
                  {label}
                </span>
              </Command.Item>
            ))}
          </Command.Group>
          <Command.Group heading="Shortcuts" className="mt-1 text-xs text-muted [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5">
            {TOOLS.map((t) => (
              <Command.Item key={t.label} value={t.label} keywords={t.keywords} onSelect={() => go(t.href)} className={row}>
                <span>{t.label}</span>
                {t.hint ? <span className="text-xs text-muted">{t.hint}</span> : null}
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>
      </Command.Dialog>
    </>
  );
}
