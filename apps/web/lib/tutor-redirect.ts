/**
 * The four tutor tools used to be tabs on /tutor (`?tool=`); each now has its own page. Where an old
 * /tutor link goes: the tool's page, with the other query parameters (for example `topic`) kept and the
 * `tool` parameter dropped, since the new pages do not read it.
 */
const TOOL_PAGES = {
  map: "/concept-map",
  socratic: "/work-it-out",
  synthesis: "/compare",
  adaptive: "/explain",
} as const;

export function legacyTutorTarget(search: URLSearchParams): string {
  const params = new URLSearchParams(search);
  const tool = params.get("tool") ?? "";
  params.delete("tool");
  const path = Object.hasOwn(TOOL_PAGES, tool) ? TOOL_PAGES[tool as keyof typeof TOOL_PAGES] : TOOL_PAGES.map;
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}
