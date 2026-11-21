import { BarChart3, Bot, Code2, FolderOpen, MessageSquare, Orbit, Sigma, Brain, Layers, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Name in the command palette when it differs from `label` (the top bar calls /sources "Library"). */
  paletteLabel?: string;
  /** Other words people search for, matched by word prefix in the command palette. */
  keywords?: string[];
}

export const NAV: NavItem[] = [
  { href: "/ask", label: "Ask", icon: MessageSquare, keywords: ["question", "answer", "chat", "home", "search", "cite"] },
  { href: "/sources", label: "Sources", paletteLabel: "Library (Sources)", icon: FolderOpen, keywords: ["library", "documents", "material", "pdf", "files", "upload", "index"] },
  { href: "/study", label: "Flashcards", icon: Layers, keywords: ["practice", "cards", "review", "spaced repetition", "anki", "quiz", "study"] },
  { href: "/leetcode", label: "LeetCode", icon: Code2, keywords: ["practice", "problems", "coding", "interview", "algorithms"] },
  { href: "/agent", label: "Agent", icon: Bot, keywords: ["tools", "assistant", "agentic"] },
  { href: "/tutor", label: "Tutor tools", icon: Brain, keywords: ["tools", "concept map", "socratic", "compare", "explain"] },
  { href: "/math", label: "Math", icon: Sigma, keywords: ["tools", "calculator", "equation", "solve", "algebra", "calculus", "sympy"] },
  { href: "/visualize", label: "Embedding map", icon: Orbit, keywords: ["tools", "visualize", "vectors", "embeddings", "plot", "3d"] },
  { href: "/analytics", label: "Analytics", icon: BarChart3, keywords: ["tools", "progress", "stats", "history", "usage"] },
];
