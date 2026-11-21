"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, Clock, Moon, Sun, X, Unplug } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { CommandPalette } from "@/components/command-palette";
import { SECTIONS, pagesOf, sectionCurrent, sectionFor, type Section } from "@/lib/sections";
import { api, ApiError, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";
import { plural } from "@/lib/format";
import { toggleTheme, useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export const REPO_URL = "https://github.com/moh0405/Lectern";
/** Remembered by the inline script in app/layout.tsx, which hides the strip before the first paint. */
export const DEMO_STRIP_KEY = "lectern-demo-strip-dismissed";

function ReadingTheme() {
  const theme = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return <button className="reading-theme" type="button" aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`} onClick={() => toggleTheme()}>
    {theme === "dark" ? <Sun aria-hidden="true" size={18} /> : <Moon aria-hidden="true" size={18} />}
  </button>;
}

type ApiState = "checking" | "online" | "busy" | "offline";
const ANNOUNCE: Record<Exclude<ApiState, "checking">, string> = {
  online: "Connected to the study service again.",
  busy: "Service busy · retrying shortly.",
  offline: "Offline: the study service cannot be reached.",
};

function ApiStatus() {
  const { data, isError, isPending, error } = useQuery({
    queryKey: ["health"],
    queryFn: async () => unwrap(await api.http.GET("/health")),
    refetchInterval: 30_000,
    retry: false,
  });
  const state: ApiState = isPending ? "checking" : error instanceof ApiError && error.status === 429 ? "busy" : isError ? "offline" : "online";
  // Announce changes of state only (not every 30 s poll): busy or offline whenever they start, online only on recovery.
  const [seen, setSeen] = useState<{ state: ApiState; announce: string }>({ state: "checking", announce: "" });
  if (state !== "checking" && state !== seen.state) {
    setSeen({ state, announce: state === "online" ? (seen.state === "checking" ? "" : ANNOUNCE.online) : ANNOUNCE[state] });
  }
  const text = state === "online" && data
    ? `${plural(data.chunks, "passage")} indexed · ${data.semantic_search ? "meaning search" : "keyword search"}`
    : state === "busy" ? "Service busy · retrying shortly" : state === "offline" ? "Offline" : "Connecting…";
  const Icon = state === "busy" ? Clock : state === "offline" ? Unplug : null;
  return <div className="api-status" title={data ? `Lectern API v${data.version} · ${text}` : text} data-state={state}>
    {Icon ? <Icon aria-hidden="true" className={cn("api-status-icon", state)} strokeWidth={2.2} /> : <span aria-hidden="true" className={cn("api-status-dot", state)} />}
    <span className="api-status-text">{text}</span>
    <span role="status" className="sr-only">{seen.announce}</span>
  </div>;
}

/** The pages of a multi-page section. On narrow screens it scrolls sideways, so keep the current page in view. */
function SectionBar({ section, pathname }: { section: Section; pathname: string }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const nav = ref.current;
    if (!nav) return;
    const edges = () => {
      const overflow = nav.scrollWidth > nav.clientWidth + 1;
      nav.dataset.fadeStart = String(overflow && nav.scrollLeft > 1);
      nav.dataset.fadeEnd = String(overflow && nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 1);
    };
    edges();
    nav.addEventListener("scroll", edges, { passive: true });
    const resize = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(edges);
    resize?.observe(nav);
    return () => { nav.removeEventListener("scroll", edges); resize?.disconnect(); };
  }, []);
  useEffect(() => {
    const nav = ref.current;
    const current = nav?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!nav || !current || nav.scrollWidth <= nav.clientWidth) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const left = current.offsetLeft - (nav.clientWidth - current.offsetWidth) / 2;
    nav.scrollTo({ left: Math.max(0, left), behavior: reduce ? "auto" : "smooth" });
  }, [pathname]);
  return <nav ref={ref} aria-label={`${section.label} pages`} className="desk-subnav">
    {pagesOf(section).map(item => {
      const Icon = item.icon;
      const active = pathname === item.href || pathname.startsWith(item.href + "/");
      return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className="desk-subnav-link"><Icon aria-hidden="true" strokeWidth={1.7} />{item.label}</Link>;
    })}
  </nav>;
}

/** Public demo notice: slim, dismissible, remembered in this browser. */
function DemoStrip() {
  const hide = () => {
    document.documentElement.dataset.demoStrip = "dismissed";
    try { localStorage.setItem(DEMO_STRIP_KEY, "1"); } catch { /* Hidden for this visit only. */ }
    document.getElementById("workspace-content")?.focus({ preventScroll: true });
  };
  return <div className="demo-strip" role="region" aria-label="About this demo">
    <p className="demo-strip-text">
      <strong className="demo-strip-label">Public demo</strong>
      <span className="demo-strip-sep" aria-hidden="true">·</span>
      <span>Ask the shared CS textbooks, or add your own PDF (it stays in your browser)</span>
      <span className="demo-strip-sep" aria-hidden="true">·</span>
      <a href={`${REPO_URL}#readme`} target="_blank" rel="noreferrer">How it works</a>
      <span className="demo-strip-sep" aria-hidden="true">·</span>
      <a href={REPO_URL} target="_blank" rel="noreferrer">Source code</a>
    </p>
    <button type="button" className="demo-strip-close" aria-label="Hide the demo notice" title="Hide the demo notice" onClick={hide}><X aria-hidden="true" size={15} /></button>
  </div>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const demo = useDemo();
  const section = sectionFor(pathname);
  const multiPage = section && section.paths.length > 1 ? section : null;
  // The Ask page is the Evidence Desk: full width, with its own columns. Other pages keep a readable column.
  const desk = pathname === "/ask";
  return <div className="lectern-app">
    <a className="workspace-skip" href="#workspace-content">Skip to content</a>
    <header className="desk-header">
      {demo ? <DemoStrip /> : null}
      <Link href="/ask" className="desk-brand" aria-label="Lectern home"><span className="desk-brand-mark"><BookOpen aria-hidden="true" size={21} strokeWidth={1.6} /></span>Lectern</Link>
      <nav aria-label="Main" className="desk-nav">
        {SECTIONS.map(s => {
          const current = sectionCurrent(s, pathname);
          return <Link key={s.label} href={s.href} aria-current={current} className={cn("desk-nav-link", current && "active")}>{s.label}</Link>;
        })}
      </nav>
      <div className="desk-actions"><ApiStatus /><CommandPalette /><ReadingTheme /></div>
    </header>
    {multiPage ? <SectionBar section={multiPage} pathname={pathname} /> : null}
    <main id="workspace-content" tabIndex={-1} className={desk ? "desk-main" : "workspace-content"}>{children}</main>
    {desk ? null : <footer className="workspace-footer"><span>Lectern<span className="workspace-footer-separator">/</span>An AI tutor that shows its sources.</span><span>Every answer cites the passage it came from.</span></footer>}
  </div>;
}
