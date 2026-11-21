import Link from "next/link";
import { NAV } from "@/lib/nav";
import { SECTIONS } from "@/lib/sections";

const BLURB: Record<string, string> = {
  Ask: "Ask a question; the answer cites its sources.",
  Library: "Add and manage the material Lectern answers from.",
  Practice: "Flashcards and LeetCode problems.",
  Tools: "Tutor tools, math, the agent, the map and analytics.",
};

/** The four sections as large links, for pages that have lost their way (404, error). */
export function SectionLinks() {
  return (
    <nav aria-label="Sections" className="status-page-sections">
      <h2 className="eyebrow">Or go to a section</h2>
      <ul className="status-page-links">
        {SECTIONS.map((s) => {
          const Icon = NAV.find((n) => n.href === s.href)?.icon;
          return (
            <li key={s.label}>
              <Link href={s.href} className="status-page-link">
                {Icon ? <Icon aria-hidden="true" strokeWidth={1.7} /> : null}
                <span>
                  <span className="status-page-link-title">{s.label}</span>
                  <span className="status-page-link-blurb">{BLURB[s.label]}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function StatusPageHint() {
  return (
    <p className="status-page-hint">
      Looking for a particular tool? Press <kbd>Ctrl</kbd> <kbd>K</kbd> (<kbd>⌘</kbd> <kbd>K</kbd> on a Mac) to search every page.
    </p>
  );
}
