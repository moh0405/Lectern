import { NAV, type NavItem } from "@/lib/nav";

/** The four top-level areas of Lectern. Every page in `NAV` belongs to exactly one. */
export interface Section {
  label: "Ask" | "Library" | "Practice" | "Tools";
  /** Where the section's top-level link goes. */
  href: string;
  /** The section's pages, in the order the section bar and the command palette list them. */
  paths: string[];
}

export const SECTIONS: Section[] = [
  { label: "Ask", href: "/ask", paths: ["/ask"] },
  { label: "Library", href: "/sources", paths: ["/sources"] },
  { label: "Practice", href: "/study", paths: ["/study", "/leetcode"] },
  { label: "Tools", href: "/tutor", paths: ["/tutor", "/math", "/agent", "/visualize", "/analytics"] },
];

const inPath = (pathname: string, path: string) => pathname === path || pathname.startsWith(path + "/");

export function sectionFor(pathname: string): Section | undefined {
  return SECTIONS.find((s) => s.paths.some((p) => inPath(pathname, p)));
}

/** The `NAV` entries of a section, in section order. */
export function pagesOf(section: Section): NavItem[] {
  return section.paths.map((p) => NAV.find((n) => n.href === p)).filter((n): n is NavItem => Boolean(n));
}

/**
 * `aria-current` for a top-level section link: "page" when the link's own page is open, "true" on the
 * section's other pages (so assistive tech still hears which section is current), otherwise nothing.
 */
export function sectionCurrent(section: Section, pathname: string): "page" | "true" | undefined {
  if (pathname === section.href) return "page";
  return sectionFor(pathname) === section ? "true" : undefined;
}
