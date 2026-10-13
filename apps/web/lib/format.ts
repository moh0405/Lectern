/** "1 chunk", "2 chunks" */
export function plural(n: number, singular: string, pluralForm = `${singular}s`): string {
  return `${n.toLocaleString()} ${n === 1 ? singular : pluralForm}`;
}

/** "page 132" or, for a passage that runs onto the next page, "pages 132–133". Empty when there is no page. */
export function pageLabel(page?: number | null, endPage?: number | null, short = false): string {
  if (!page) return "";
  const range = endPage && endPage !== page;
  if (short) return range ? `pp.${page}–${endPage}` : `p.${page}`;
  return range ? `pages ${page}–${endPage}` : `page ${page}`;
}
