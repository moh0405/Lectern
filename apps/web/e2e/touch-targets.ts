import type { Page } from "@playwright/test";

/** A phone: 390 px wide with a touch screen, so `(pointer: coarse)` styles apply. */
export const PHONE = { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } as const;

/**
 * Interactive elements on the page smaller than 44x44 px (WCAG 2.5.5 target size), as "name WxH" strings.
 * A checkbox or radio is measured by its label (the label is what a finger hits). Not counted: links inside
 * a sentence (WCAG's inline exception), the visually hidden file input (its visible button is counted),
 * anything hidden or inert, and selectors in `skip`.
 */
export async function smallTouchTargets(page: Page, skip: string[] = []): Promise<string[]> {
  return page.evaluate((skip) => {
    const SELECTOR = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [role=radio], [role=checkbox], [role=switch]';
    const inProse = (el: Element) => {
      if (el.tagName !== "A") return false;
      const block = el.closest("p, li, dd, td, blockquote");
      return !!block && (block.textContent ?? "").trim().length > (el.textContent ?? "").trim().length;
    };
    const out: string[] = [];
    for (const el of document.querySelectorAll<HTMLElement>(SELECTOR)) {
      if (skip.some((s) => el.matches(s))) continue;
      if (el.closest("[aria-hidden=true], [inert], details:not([open]) > :not(summary)")) continue;
      if (el instanceof HTMLInputElement && el.type === "file" && el.classList.contains("sr-only")) continue;
      if (inProse(el)) continue;
      const target = el instanceof HTMLInputElement && (el.type === "checkbox" || el.type === "radio") ? (el.closest("label") ?? el) : el;
      const box = target.getBoundingClientRect();
      if (box.width === 0 || box.height === 0 || getComputedStyle(el).visibility === "hidden") continue;
      // Half a pixel of rounding is fine (44px boxes can measure 43.99).
      if (box.width < 43.5 || box.height < 43.5) {
        const name = (el.getAttribute("aria-label") || el.textContent || el.getAttribute("placeholder") || el.tagName).trim().replace(/\s+/g, " ").slice(0, 40);
        out.push(`${el.tagName.toLowerCase()} "${name}" ${Math.round(box.width)}x${Math.round(box.height)}`);
      }
    }
    return out;
  }, skip);
}
