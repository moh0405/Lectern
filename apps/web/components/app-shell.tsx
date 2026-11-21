"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore, type ReactNode } from "react";
import { CommandPalette } from "@/components/command-palette";
import { NAV } from "@/lib/nav";
import { SECTIONS, sectionFor } from "@/lib/sections";
import { api, ApiError, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";

const THEME_KEY = "lectern-reading-theme";
function subscribeTheme(update: () => void) {
  const storage = (event: StorageEvent) => {
    if (event.key !== THEME_KEY && event.key !== null) return;
    document.documentElement.dataset.theme = event.newValue === "light" ? "light" : "dark";
    update();
  };
  window.addEventListener("storage", storage);
  window.addEventListener("lectern-theme-change", update);
  return () => { window.removeEventListener("storage", storage); window.removeEventListener("lectern-theme-change", update); };
}
function getTheme() {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}
function ReadingTheme() {
  const theme = useSyncExternalStore(subscribeTheme, getTheme, () => "dark");
  const next = theme === "dark" ? "light" : "dark";
  return <button className="reading-theme" type="button" aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`} onClick={() => {
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(THEME_KEY, next); } catch { /* Theme still works when storage is unavailable. */ }
    window.dispatchEvent(new Event("lectern-theme-change"));
  }}>{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>;
}

function ApiStatus() {
  const { data, isError, isPending, error } = useQuery({
    queryKey: ["health"],
    queryFn: async () => unwrap(await api.http.GET("/health")),
    refetchInterval: 30_000,
    retry: false,
  });
  const state = isPending ? "checking" : error instanceof ApiError && error.status === 429 ? "busy" : isError ? "offline" : "online";
  const text = state === "online" && data ? `${plural(data.chunks, "chunk")} · ${data.semantic_search ? "semantic" : "keyword"} search` : state === "busy" ? "Service busy · retrying shortly" : state === "offline" ? "API offline" : "Connecting…";
  return <div className="api-status" title={data ? `API v${data.version} · ${text}` : text} role="status">
    <span aria-hidden="true" className={cn("api-status-dot", state)} />
    <span className="api-status-text">{text}</span>
  </div>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const section = sectionFor(pathname);
  const pages = section && section.paths.length > 1 ? section.paths.map(p => NAV.find(n => n.href === p)!) : [];
  // The Ask page is the Evidence Desk: full width, with its own columns. Other pages keep a readable column.
  const desk = pathname === "/ask";
  return <div className="lectern-app">
    <a className="workspace-skip" href="#workspace-content">Skip to content</a>
    <header className="desk-header">
      <Link href="/ask" className="desk-brand" aria-label="Lectern home"><span className="desk-brand-mark"><BookOpen size={21} strokeWidth={1.6} /></span>Lectern</Link>
      <nav aria-label="Main" className="desk-nav">
        {SECTIONS.map(s => {
          const active = s === section;
          return <Link key={s.label} href={s.href} aria-current={active && pathname === s.href ? "page" : undefined} className={cn("desk-nav-link", active && "active")}>{s.label}</Link>;
        })}
      </nav>
      <div className="desk-actions"><ApiStatus /><CommandPalette /><ReadingTheme /></div>
    </header>
    {pages.length ? <nav aria-label={`${section!.label} pages`} className="desk-subnav">
      {pages.map(item => {
        const Icon = item.icon;
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className="desk-subnav-link"><Icon aria-hidden="true" strokeWidth={1.7} />{item.label}</Link>;
      })}
    </nav> : null}
    <main id="workspace-content" tabIndex={-1} className={desk ? "desk-main" : "workspace-content"}>{children}</main>
    {desk ? null : <footer className="workspace-footer"><span>Lectern<span className="workspace-footer-separator">/</span>An AI tutor that shows its sources.</span><span>Every answer cites the passage it came from.</span></footer>}
  </div>;
}
