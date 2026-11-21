import {
  BarChart3,
  Bot,
  Code2,
  FolderOpen,
  GitCompare,
  GraduationCap,
  Layers,
  Lightbulb,
  MessageSquare,
  Network,
  Orbit,
  Sigma,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Name in the command palette when it differs from `label` (the top bar calls /sources "Library"). */
  paletteLabel?: string;
  /** Other words people search for, matched by word prefix in the command palette. */
  keywords?: string[];
}

/** Every page in the app. `lib/sections.ts` decides which section each belongs to and in what order. */
export const NAV: NavItem[] = [
  // Ask
  { href: "/ask", label: "Ask", icon: MessageSquare, keywords: ["question", "answer", "chat", "home", "search", "cite"] },
  // Library
  { href: "/sources", label: "Sources", paletteLabel: "Library (Sources)", icon: FolderOpen, keywords: ["library", "documents", "material", "pdf", "files", "upload", "index"] },
  { href: "/visualize", label: "Map", paletteLabel: "Map (embeddings)", icon: Orbit, keywords: ["embedding map", "embeddings", "vectors", "visualize", "plot", "3d", "library"] },
  { href: "/analytics", label: "Insights", icon: BarChart3, keywords: ["analytics", "stats", "usage", "progress", "history", "latency", "library"] },
  // Practice
  { href: "/study", label: "Flashcards", icon: Layers, keywords: ["practice", "cards", "review", "spaced repetition", "anki", "quiz", "study"] },
  { href: "/leetcode", label: "LeetCode", icon: Code2, keywords: ["practice", "problems", "coding", "interview", "algorithms"] },
  { href: "/work-it-out", label: "Work it out", icon: Lightbulb, keywords: ["socratic", "hints", "tutor", "guide", "guiding questions", "stuck", "practice"] },
  { href: "/explain", label: "Explain at my level", icon: GraduationCap, keywords: ["eli5", "level", "adaptive", "simple", "expert", "beginner", "practice"] },
  // Tools
  { href: "/concept-map", label: "Concept map", icon: Network, keywords: ["graph", "diagram", "topic", "concepts", "mind map", "tools"] },
  { href: "/compare", label: "Compare sources", icon: GitCompare, keywords: ["synthesis", "documents", "contrast", "agree", "differ", "tools"] },
  { href: "/agent", label: "Agent", icon: Bot, keywords: ["tools", "assistant", "agentic"] },
  { href: "/math", label: "Math", icon: Sigma, keywords: ["tools", "calculator", "equation", "solve", "algebra", "calculus", "sympy"] },
];
