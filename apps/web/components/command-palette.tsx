"use client";

import { Command } from "cmdk";
import { MessageSquare, Moon, Plus, Search, Sun, type LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { SECTIONS, pagesOf, sectionFor } from "@/lib/sections";
import { toggleTheme, useTheme } from "@/lib/theme";

type Run = { href: string } | { action: "theme" };

export interface PaletteItem {
  id: string;
  label: string;
  hint?: string;
  keywords?: string[];
  icon?: LucideIcon;
  run: Run;
}

/** Shortcuts into a page, listed under the section their page belongs to. */
const SHORTCUTS: Omit<PaletteItem, "id">[] = [
  { label: "Concept map", hint: "Tutor tools", run: { href: "/tutor" }, keywords: ["graph", "diagram", "topic"] },
  { label: "Socratic tutor", hint: "Tutor tools", run: { href: "/tutor?tool=socratic" }, keywords: ["hints", "guide", "questions"] },
  { label: "Compare sources", hint: "Tutor tools", run: { href: "/tutor?tool=synthesis" }, keywords: ["synthesis", "documents", "contrast"] },
  { label: "Explain at my level", hint: "Tutor tools", run: { href: "/tutor?tool=adaptive" }, keywords: ["eli5", "adaptive", "simple"] },
  { label: "Upload a PDF", hint: "Library", run: { href: "/sources" }, keywords: ["file", "audio", "add", "document"] },
  { label: "Add a link", hint: "Library", run: { href: "/sources" }, keywords: ["youtube", "github", "url", "web"] },
  { label: "Hard tree problems", hint: "LeetCode", run: { href: "/leetcode?d=Hard&t=Tree" }, keywords: ["practice"] },
  { label: "Easy array problems", hint: "LeetCode", run: { href: "/leetcode?d=Easy&t=Array" }, keywords: ["practice"] },
];

interface Group {
  heading: string;
  items: PaletteItem[];
}

/** Pages and shortcuts grouped by top-level section, in `SECTIONS` order. */
export const SECTION_GROUPS: Group[] = SECTIONS.map((section) => ({
  heading: section.label,
  items: [
    ...pagesOf(section).map((page) => ({
      id: `page:${page.href}`,
      label: page.paletteLabel ?? page.label,
      keywords: [section.label, page.label, ...(page.keywords ?? [])],
      icon: page.icon,
      run: { href: page.href },
    })),
    ...SHORTCUTS.filter((s) => "href" in s.run && sectionFor(new URL(s.run.href, "http://x").pathname) === section).map((s) => ({
      ...s,
      id: `shortcut:${s.label}`,
      keywords: [section.label, ...(s.keywords ?? [])],
    })),
  ],
}));

const words = (text: string) => text.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);

/**
 * How well `item` matches what was typed, 0 meaning "hide". Every typed word must start a word of the
 * label or a keyword (or appear inside the label), so "practice" does not fuzzily match "Compare sources".
 */
export function scoreItem(item: Pick<PaletteItem, "label" | "keywords">, search: string): number {
  const typed = words(search);
  if (!typed.length) return 1;
  const label = item.label.toLowerCase();
  const labelWords = words(item.label);
  const keywordWords = (item.keywords ?? []).flatMap(words);
  let total = 0;
  for (const t of typed) {
    if (label.startsWith(t)) total += 1;
    else if (labelWords.some((w) => w.startsWith(t))) total += 0.8;
    else if (keywordWords.some((w) => w.startsWith(t))) total += 0.6;
    else if (label.replace(/[^a-z0-9]/g, "").includes(t)) total += 0.4;
    else return 0;
  }
  return total / typed.length;
}

function filterGroups(groups: Group[], search: string): Group[] {
  if (!search.trim()) return groups;
  return groups
    .map((g) => {
      const scored = g.items.map((item, i) => ({ item, i, s: scoreItem(item, search) })).filter((x) => x.s > 0);
      scored.sort((a, b) => b.s - a.s || a.i - b.i);
      return { heading: g.heading, items: scored.map((x) => x.item), best: scored[0]?.s ?? 0 };
    })
    .filter((g) => g.items.length)
    .sort((a, b) => b.best - a.best)
    .map(({ heading, items }) => ({ heading, items }));
}

/** Focus the main region (after the palette navigates), so keyboard and screen-reader users land on the new page. */
function focusMain() {
  document.getElementById("workspace-content")?.focus({ preventScroll: true });
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const router = useRouter();
  const theme = useTheme();
  const opener = useRef<HTMLElement | null>(null);
  const afterClose = useRef<(() => void) | null>(null);

  const openPalette = () => {
    opener.current = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : null;
    setSearch("");
    setOpen(true);
  };

  const close = (then?: () => void) => {
    afterClose.current = then ?? (() => opener.current?.focus({ preventScroll: true }));
    setOpen(false);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (open) close();
        else openPalette();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // The dialog unmounts its focus trap on close and would leave focus on <body>: put it back once that is done.
  useEffect(() => {
    if (open) return;
    const then = afterClose.current;
    afterClose.current = null;
    if (!then) return;
    const id = window.setTimeout(then, 0);
    return () => window.clearTimeout(id);
  }, [open]);

  const next = theme === "dark" ? "light" : "dark";
  const typed = search.trim();
  const actions: PaletteItem[] = useMemo(
    () => [
      { id: "action:theme", label: `Switch to ${next} theme`, keywords: ["theme", "dark", "light", "mode", "appearance", "colour", "color", "reading"], icon: next === "light" ? Sun : Moon, run: { action: "theme" } },
      { id: "action:add", label: "Add material", hint: "Library", keywords: ["upload", "pdf", "file", "document", "source", "link", "import", "new"], icon: Plus, run: { href: "/sources" } },
    ],
    [next],
  );
  const groups = filterGroups([...SECTION_GROUPS, { heading: "Actions", items: actions }], search);
  const ask: PaletteItem | null = typed ? { id: "action:ask", label: `Ask: ${typed}`, icon: MessageSquare, run: { href: `/ask?q=${encodeURIComponent(typed)}` } } : null;
  if (ask) {
    // Asking is always possible; it comes first only when no page or tool matches.
    const actionsGroup = groups.find((g) => g.heading === "Actions");
    if (actionsGroup) actionsGroup.items.push(ask);
    else groups.push({ heading: "Actions", items: [ask] });
  }
  const nothingElse = Boolean(typed) && groups.every((g) => g.items.every((i) => i === ask));

  const run = (item: PaletteItem) => {
    if ("action" in item.run) {
      close(() => {
        toggleTheme();
        opener.current?.focus({ preventScroll: true });
      });
      return;
    }
    const href = item.run.href;
    close(focusMain);
    router.push(href);
  };

  const row = "flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-md px-3 py-2 text-sm text-fg aria-selected:bg-accent/15";
  const heading = "text-xs text-muted [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.14em]";
  return (
    <>
      <button
        type="button"
        onClick={openPalette}
        className="workspace-jump"
        aria-label="Find a page or tool"
        aria-keyshortcuts="Control+K Meta+K"
        aria-haspopup="dialog"
      >
        <Search aria-hidden="true" className="h-3.5 w-3.5" />
        <span className="flex-1 text-left">Find a page or tool</span>
        <kbd aria-hidden="true" className="rounded border border-border px-1.5 font-mono">⌘ / Ctrl K</kbd>
      </button>
      <Command.Dialog
        open={open}
        onOpenChange={(o) => (o ? openPalette() : close())}
        label="Command palette"
        shouldFilter={false}
        loop
        overlayClassName="fixed inset-0 z-40 bg-black/60"
        contentClassName="fixed left-1/2 top-[12%] z-50 w-[min(92vw,34rem)] -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
      >
        <Command.Input
          autoFocus
          value={search}
          onValueChange={setSearch}
          placeholder="Go to a page or tool, or type a question…"
          className="w-full border-b border-border bg-transparent px-4 py-3 text-base text-fg outline-none placeholder:text-muted"
        />
        <Command.List className="max-h-[min(24rem,60dvh)] overflow-y-auto p-2">
          {nothingElse ? <p className="px-3 pb-1 pt-3 text-sm text-muted">Nothing matches. You can ask it as a question:</p> : null}
          {groups.map((g) => (
            <Command.Group key={g.heading} heading={g.heading} className={heading}>
              {g.items.map((item) => {
                const Icon = item.icon;
                return (
                  <Command.Item key={item.id} value={item.id} onSelect={() => run(item)} className={row}>
                    <span className="flex min-w-0 items-center gap-2">
                      {Icon ? <Icon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" /> : <span aria-hidden="true" className="w-4 shrink-0" />}
                      <span className="truncate">{item.label}</span>
                    </span>
                    {item.hint ? <span className="shrink-0 text-xs text-muted">{item.hint}</span> : null}
                  </Command.Item>
                );
              })}
            </Command.Group>
          ))}
        </Command.List>
        <p className="border-t border-border px-4 py-2 font-mono text-[10px] text-muted">
          <span className="sr-only">Keys: </span>↑ ↓ to move · Enter to open · Esc to close
        </p>
      </Command.Dialog>
    </>
  );
}
