/** The four top-level areas of Lectern. Every page in `NAV` belongs to exactly one. */
export interface Section {
  label: "Ask" | "Library" | "Practice" | "Tools";
  /** Where the section's top-level link goes. */
  href: string;
  paths: string[];
}

export const SECTIONS: Section[] = [
  { label: "Ask", href: "/ask", paths: ["/ask"] },
  { label: "Library", href: "/sources", paths: ["/sources"] },
  { label: "Practice", href: "/study", paths: ["/study", "/leetcode"] },
  { label: "Tools", href: "/tutor", paths: ["/tutor", "/math", "/agent", "/visualize", "/analytics"] },
];

export function sectionFor(pathname: string): Section | undefined {
  return SECTIONS.find((s) => s.paths.some((p) => pathname === p || pathname.startsWith(p + "/")));
}
