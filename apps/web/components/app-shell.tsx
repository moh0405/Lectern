"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, BookOpen, ChevronRight, Menu, Moon, Sun, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { CommandPalette } from "@/components/command-palette";
import { NAV } from "@/lib/nav";
import { api, ApiError, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";
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
  return <div className="api-status" title={data ? `API v${data.version}` : undefined} role="status">
    <span aria-hidden="true" className={cn("api-status-dot", state)} />
    {state === "online" && data ? `${plural(data.chunks, "chunk")} · ${data.semantic_search ? "semantic" : "keyword"} search` : state === "busy" ? "Service busy · retrying shortly" : state === "offline" ? "API offline" : "Connecting…"}
  </div>;
}

const GROUPS = [
  { name: "Your workspace", paths: ["/ask", "/sources"] },
  { name: "Learn & practice", paths: ["/study", "/tutor", "/math", "/leetcode"] },
  { name: "Explore the system", paths: ["/agent", "/visualize", "/analytics"] },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const demo = useDemo();
  const [expandedPath, setExpandedPath] = useState<string | null>(null);
  const expanded = expandedPath === pathname;
  const menuRef = useRef<HTMLButtonElement>(null);
  const current = NAV.find(n => pathname === n.href || pathname.startsWith(n.href + "/"));
  return <div className="lectern-workspace">
    <a className="workspace-skip" href="#workspace-content">Skip to content</a>
    <aside className="workspace-sidebar" data-expanded={expanded} onKeyDown={e => { if (e.key === "Escape" && expanded) { setExpandedPath(null); menuRef.current?.focus(); } }}>
      <div className="workspace-brand-row">
        <Link href="/ask" className="workspace-brand" aria-label="Lectern home"><span className="workspace-brand-mark"><BookOpen size={23} strokeWidth={1.6} /></span><span>Lectern<small>Your material. Understood.</small></span></Link>
        <button className="workspace-menu" type="button" ref={menuRef} aria-controls="workspace-navigation" aria-expanded={expanded} onClick={() => setExpandedPath(expanded ? null : pathname)}>{expanded ? <X size={18} /> : <Menu size={18} />}<span>{expanded ? "Close tools" : "All tools"}</span></button>
      </div>
      <nav aria-label="Main" id="workspace-navigation" className="workspace-navigation">
        {GROUPS.map(group => <div className="workspace-nav-group" key={group.name}>
          <p className="workspace-nav-caption">{group.name}</p>
          {group.paths.map(path => {
            const item = NAV.find(n => n.href === path)!;
            const active = pathname === path || pathname.startsWith(path + "/");
            const Icon = item.icon;
            return <Link key={path} href={path} aria-current={active ? "page" : undefined} onClick={() => setExpandedPath(null)} className={cn("workspace-nav-link", active && "active")}><Icon size={17} strokeWidth={1.65} /><span>{item.label}</span>{active ? <span className="workspace-nav-indicator" aria-hidden="true" /> : null}</Link>;
          })}
        </div>)}
      </nav>
      <div className="workspace-sidebar-footer">
        <div className="workspace-library-note"><span className="workspace-note-icon"><BookOpen size={17} /></span><strong>{demo ? "A personal study space" : "Grounded in your sources"}</strong><p>{demo ? "Add your documents. Keep them in your browser." : "Turn your material into something you understand."}</p><Link href="/sources">Open your library <ArrowUpRight size={14} /></Link></div>
        <ApiStatus />
      </div>
    </aside>
    <div className="workspace-body">
      <div className="workspace-toolbar"><div className="workspace-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>{current?.label ?? "Lectern"}</strong></div><div className="workspace-toolbar-actions"><CommandPalette /><ReadingTheme /></div></div>
      <main id="workspace-content" tabIndex={-1} className="workspace-content">{children}</main>
      <footer className="workspace-footer"><span>Lectern<span className="workspace-footer-separator">/</span>Learn from the source.</span><span>Built for a little more understanding.</span></footer>
    </div>
  </div>;
}
