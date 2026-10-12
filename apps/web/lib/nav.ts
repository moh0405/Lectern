import { BarChart3, Code2, FolderOpen, MessageSquare, Orbit, Sigma, Brain, type LucideIcon } from "lucide-react";

export interface NavItem {
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
  { href: "/visualize", label: "Embedding map", icon: Orbit },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];
