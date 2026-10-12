"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  BookOpen,
  Brain,
  Code2,
  FolderOpen,
  MessageSquare,
  Sigma,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { api, unwrap } from "@/lib/api";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV: NavItem[] = [
  { href: "/ask", label: "Ask", icon: MessageSquare },
  { href: "/sources", label: "Sources", icon: FolderOpen },
  { href: "/leetcode", label: "LeetCode", icon: Code2 },
  { href: "/tutor", label: "Tutor tools", icon: Brain },
  { href: "/math", label: "Math", icon: Sigma },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

function ApiStatus() {
  const { data, isError, isPending } = useQuery({
    queryKey: ["health"],
    queryFn: async () => unwrap(await api.http.GET("/health")),
    refetchInterval: 30_000,
    retry: false,
  });
  const state = isPending ? "checking" : isError ? "offline" : "online";
  return (
    <div className="flex items-center gap-2 text-xs text-muted" title={data ? `API v${data.version}` : undefined}>
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          state === "online" && "bg-good",
          state === "offline" && "bg-bad",
          state === "checking" && "animate-pulse bg-warn",
        )}
      />
      {state === "online" && data
        ? `${data.chunks.toLocaleString()} chunks · ${data.semantic_search ? "semantic" : "keyword"} search`
        : state === "offline"
          ? "API offline"
          : "Connecting…"}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="mx-auto flex min-h-dvh max-w-7xl flex-col md:flex-row">
      <aside className="border-b border-border md:sticky md:top-0 md:h-dvh md:w-60 md:shrink-0 md:border-b-0 md:border-r">
        <div className="flex items-center gap-2 px-4 py-4">
          <BookOpen className="h-5 w-5 text-accent-2" />
          <span className="font-semibold tracking-tight">AI Study Mentor</span>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:overflow-visible md:pb-0">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                  active ? "bg-accent/20 text-fg" : "text-muted hover:bg-surface-2 hover:text-fg",
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="hidden px-4 py-4 md:absolute md:bottom-0 md:block">
          <ApiStatus />
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8">
        <div className="mb-4 md:hidden">
          <ApiStatus />
        </div>
        {children}
      </main>
    </div>
  );
}
