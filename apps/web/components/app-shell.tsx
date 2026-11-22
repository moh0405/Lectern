"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "@ai-study-mentor/api-client";
import { BookOpen, Clock, Moon, Sun, X, Unplug } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { CommandPalette } from "@/components/command-palette";
import { SECTIONS, pagesOf, sectionCurrent, sectionFor, type Section } from "@/lib/sections";
import { api, unwrap } from "@/lib/api";
import { apiStateOf, nextCheckDelay, outcomeOfError, recordHealth, type ApiState, type HealthOutcome, type HealthStreak } from "@/lib/api-status";
import { useDemo } from "@/lib/demo";
import { plural } from "@/lib/format";
import { toggleTheme, useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

type Health = components["schemas"]["Health"];

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

const ANNOUNCE: Record<Exclude<ApiState, "checking">, string> = {
  starting: "The study service is starting up. This can take a few seconds.",
  online: "Connected to the study service again.",
  busy: "Service busy · retrying shortly.",
  offline: "Offline: the study service cannot be reached.",
};

/** Queries that show what the service holds; refetched when it comes back, so pages do not keep a stale or failed answer. */
const METADATA_KEYS = new Set(["documents", "stats", "suggestions"]);

/** The latest health report (kept through failed checks), the streak of checks, and the light it means. */
interface HealthCheck { health: Health | null; streak: HealthStreak; state: ApiState }

function useHealth(): HealthCheck | undefined {
  const qc = useQueryClient();
  const { data, refetch } = useQuery({
    queryKey: ["health"],
    // Never throws: a failed check is a result ("starting", "busy" or eventually "offline"), and the schedule below
    // re-checks quickly while the service wakes up instead of retrying inside one query.
    queryFn: async (): Promise<HealthCheck> => {
      const prev = qc.getQueryData<HealthCheck>(["health"]);
      let health: Health | null = prev?.health ?? null;
      let outcome: HealthOutcome;
      try {
        health = unwrap(await api.http.GET("/health"));
        outcome = health.status === "starting" ? "starting" : "ok";
      } catch (e) {
        outcome = outcomeOfError(e);
      }
      const now = Date.now();
      const streak = recordHealth(prev?.streak, outcome, now);
      return { health, streak, state: apiStateOf(streak, now) };
    },
    retry: false,
    refetchInterval: (query) => nextCheckDelay(query.state.data?.streak, Date.now()),
  });
  const state = data?.state;
  // A returning tab or network may find the service back (or gone): look now rather than at the next scheduled check.
  useEffect(() => {
    const now = () => void refetch();
    const back = () => { if (document.visibilityState === "visible" && state !== "online") void refetch(); };
    window.addEventListener("online", now);
    window.addEventListener("focus", back);
    document.addEventListener("visibilitychange", back);
    return () => {
      window.removeEventListener("online", now);
      window.removeEventListener("focus", back);
      document.removeEventListener("visibilitychange", back);
    };
  }, [refetch, state]);
  // Back online after a wait: refresh what pages read from the service (counts, document lists, failed loads).
  const previous = useRef(state);
  useEffect(() => {
    const was = previous.current;
    previous.current = state;
    if (state !== "online" || was === undefined || was === "online" || was === "checking") return;
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "health" && (q.state.status === "error" || METADATA_KEYS.has(String(q.queryKey[0]))) });
  }, [qc, state]);
  return data;
}

function ApiStatus() {
  const check = useHealth();
  const state: ApiState = check?.state ?? "checking";
  const data = state === "online" ? check?.health : null;
  // Announce changes of state only (not every 30 s poll): busy or offline whenever they start, online only on recovery.
  const [seen, setSeen] = useState<{ state: ApiState; announce: string }>({ state: "checking", announce: "" });
  if (state !== "checking" && state !== seen.state) {
    setSeen({ state, announce: state === "online" ? (seen.state === "checking" ? "" : ANNOUNCE.online) : ANNOUNCE[state] });
  }
  const text = state === "online" && data
    ? `${plural(data.chunks ?? 0, "passage")} indexed · ${data.semantic_search ? "meaning search" : "keyword search"}`
    : state === "busy" ? "Service busy · retrying shortly" : state === "offline" ? "Offline" : state === "starting" ? "Starting up…" : "Connecting…";
  // Mid-width headers show this instead; the full text stays in the accessibility tree and the tooltip.
  const short = state === "online" && data ? `${plural(data.chunks ?? 0, "passage")} indexed` : state === "busy" ? "Service busy" : text;
  const Icon = state === "busy" ? Clock : state === "offline" ? Unplug : null;
  const title = state === "starting" ? "The study service is waking up. This usually takes a few seconds."
    : state === "offline" ? "The study service cannot be reached. Lectern keeps checking and reconnects by itself."
    : data ? `Lectern API v${data.version} · ${text}` : text;
  return <div className="api-status" title={title} data-state={state}>
    {Icon ? <Icon aria-hidden="true" className={cn("api-status-icon", state)} strokeWidth={2.2} /> : <span aria-hidden="true" className={cn("api-status-dot", state)} />}
    <span className="api-status-text">{text}</span>
    {short !== text ? <span aria-hidden="true" className="api-status-short">{short}</span> : null}
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
      <span className="demo-strip-sep" aria-hidden="true"> · </span>
      <span className="demo-strip-long">Ask the shared CS textbooks, or add your own PDF (it stays in your browser)</span>
      <span className="demo-strip-short">Your own PDFs stay in your browser</span>
      <span className="demo-strip-links">
        <span className="demo-strip-sep" aria-hidden="true"> · </span>
        <a href={`${REPO_URL}#readme`} target="_blank" rel="noreferrer">How it works</a>
        <span className="demo-strip-sep" aria-hidden="true"> · </span>
        <a href={REPO_URL} target="_blank" rel="noreferrer">Source code</a>
      </span>
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
