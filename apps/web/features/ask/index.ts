/**
 * Pieces of the Evidence Desk other pages can reuse: link the citations in an answer, render it with citation chips,
 * and show the passage a chip points to in a source margin.
 *
 *   const linked = linkCitations(answer, citations, chunks);
 *   <CiteProvider selectedRef={selection.ref} onSelect={setSelection}>
 *     <CitedMarkdown markdown={answer} linked={linked} />
 *   </CiteProvider>
 *   <aside className="paper"><SourceMargin turn={turn} refs={linked.refs} selection={selection} onSelect={setSelection} /></aside>
 */
export { CitationChip, CitedMarkdown, CiteProvider, citationLabel, shortCiteLabel, type Selection } from "./citation-chip";
export { linkCitations, type CiteRef, type LinkedAnswer } from "./citations";
export { InlinePassage } from "./inline-passage";
export { Passage, SourceMargin } from "./source-margin";
export { groundingOf, verdictText, type Grounding } from "./grounding";
