import type { Chunk } from "@ai-study-mentor/api-client";
import type { CitationCheck } from "./session";

/**
 * Turns the citations in a finished answer into references the Evidence Desk can follow.
 *
 * The server has already checked every citation against the retrieved passages (`CitationCheck`). Here each
 * bracketed citation in the Markdown is replaced by a link to `#cite-<n>`, which the answer renders as a chip,
 * and each chip remembers which passage it points to and the sentence that cited it. Only citations the
 * server reported are linked, so ordinary brackets such as `nums[0]` are left alone. A bracket is matched to the
 * server's citations by exact label, after splitting it the way the server does (backend/citations.py).
 *
 * Some models cite in prose parentheses instead, "(*Dsa.pdf*, pages 118–120)". The server reports those parts that
 * name a retrieved document, labelled with emphasis and a leading "see" removed (`clean_paren`); here the whole
 * parenthesis becomes chips, and any part the server did not report stays as text. A bracket citation the model
 * wrapped in parentheses, "([Dsa.pdf (page 3)])", loses the parentheses, and a chip that repeats the passage of the
 * chip right before it (or of another citation in the same bracket) is dropped.
 */

export type CitationStatus = CitationCheck["status"];

export interface CiteRef {
  id: number;
  /**
   * Index into the turn's chunks, or null when there is no passage to show: always for an unverified citation, and
   * for a verified (`ok`) one whose passage cannot be found among the listed chunks.
   */
  chunk: number | null;
  label: string;
  doc: string;
  page: number | null;
  status: CitationStatus;
  /** The answer text that made this citation, used to find the closest sentence in the passage. */
  sentence: string;
}

export interface LinkedAnswer {
  markdown: string;
  refs: CiteRef[];
}

export const CITE_PREFIX = "#cite-";

// Same shape the server accepts as a citation (backend/citations.py `_BRACKET`).
const BRACKET = /(?<![\w\])])\[([^[\]\n]{3,200})\](?!\()/g;
// A prose parenthesis that may hold citations (server `_PAREN`): no brackets inside, one level of nesting, never a
// Markdown link target. Matched together with brackets so references are numbered in reading order.
const PAREN_SRC = String.raw`(?<![\]\w])\(((?:[^()[\]\n]|\([^()[\]\n]*\)){3,300})\)`;
const CITATION = new RegExp(`${BRACKET.source}|${PAREN_SRC}`, "g");
// Chips the model wrapped in parentheses, optionally after "see": "([doc (page 3)])" would render as "(01 )".
const WRAPPED_CHIPS = /\(\s*(?:(?:see(?:\s+also)?|cf\.?)\s+)?((?:\[\d+\]\(#cite-\d+\)[\s,;]*)+)\)/gi;
// Code is never rewritten: fenced blocks and inline code spans are kept as they are.
const CODE = /(```[\s\S]*?```|`[^`\n]*`)/;

const norm = (s: string) => s.trim().toLowerCase().replace(/\s+/g, " ");

const EMPHASIS = /\*+|(?<!\w)_+|_+(?!\w)|`/g;
const LEAD = /^(?:see(?:\s+also)?|cf\.?|source:|sources:|from)\s+/i;

/** A prose parenthesis as a citation label: emphasis, a leading "see" and extra spaces removed (server `clean_paren`). */
export function cleanParen(inner: string): string {
  return inner.replace(EMPHASIS, "").replace(/\s+/g, " ").trim().replace(LEAD, "").trim();
}

/** The keys a document name is known by: as written, and without its file extension (server `_doc_keys`). */
function docKeys(name: string): string[] {
  const base = norm(name);
  const stem = base.replace(/\.[a-z0-9]{1,5}$/, "");
  return stem === base ? [base] : [base, stem];
}

function sameKeys(a: string, b: string): boolean {
  const keys = docKeys(a);
  return docKeys(b).some((k) => keys.includes(k));
}

// Separators between a document and a section path, e.g. "notes.md > Hashing" (server `_SECTION_SEP`).
const SECTION_SEP = /\s*(?:>|›|»|→|\/|\||::)\s*|\s+[-–—]\s+|:\s+/;

/** The part of a citation before its first section separator, or null when there is none. */
function documentPart(doc: string): string | null {
  const m = SECTION_SEP.exec(doc);
  if (!m) return null;
  const head = doc.slice(0, m.index).trim();
  return head || null;
}

// Page lists and page suffixes, parsed as the server does (`_PAGES`, `_PAGE_LIST`, `_PAGE`, `_WITH_PAGE_*`).
const PAGES = String.raw`(?:pages?|pp?\.?)\s*\d+(?:\s*[,;&]\s*(?:(?:pages?|pp?\.?)\s*)?\d+)+`;
const PAGE_LIST = new RegExp(String.raw`^(?<doc>.+?)\s*(?:\(\s*(?<p1>${PAGES})\s*\)|[,;:·–-]\s*(?<p2>${PAGES}))\s*$`, "i");
const PAGE = String.raw`(?:pages?|pp?\.?)\s*(\d+)(?:\s*[-–]\s*(\d+))?`;
const WITH_PAGE_PAREN = new RegExp(String.raw`^(.+?)\s*\(\s*${PAGE}\s*\)\s*$`, "i");
const WITH_PAGE_COMMA = new RegExp(String.raw`^(.+?)\s*[,;:·–-]\s*${PAGE}\s*$`, "i");
const PART_SPLIT = /(?<=\))\s*[,;]\s*|\s*;\s*/;

/**
 * The citation labels the server derives from one bracket's inner text (server `_split_multi`): one label per page
 * for a page list, one per parenthesised citation, or one per retrieved document in a plain comma list.
 */
export function splitCitations(inner: string, chunkDocs: string[]): string[] {
  const text = inner.trim();
  const listed = PAGE_LIST.exec(text);
  if (listed?.groups) {
    const { doc, p1, p2 } = listed.groups;
    return ((p1 ?? p2 ?? "").match(/\d+/g) ?? []).map((n) => `${doc} (page ${n})`);
  }
  const parts = text
    .split(PART_SPLIT)
    .map((p) => p.trim())
    .filter(Boolean);
  if (parts.length > 1) return parts;
  if (text.includes(",")) {
    const pieces = text
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    if (pieces.length > 1 && pieces.every((p) => chunkDocs.some((d) => sameKeys(d, p)))) return pieces;
  }
  return [text];
}

/** The cited pages from a label such as "doc (pages 4-6)"; just the server's page when no range is written. */
function citedPages(label: string | undefined, page: number | null | undefined): [number, number] | null {
  const text = (label ?? "").trim();
  for (const pattern of [WITH_PAGE_PAREN, WITH_PAGE_COMMA]) {
    const m = pattern.exec(text);
    if (!m) continue;
    const lo = Number(m[2]);
    const hi = m[3] ? Number(m[3]) : lo;
    if (page != null && lo !== page) break; // the label disagrees with the server's page: trust the server
    return hi >= lo && hi - lo < 50 ? [lo, hi] : [lo, lo];
  }
  return page == null ? null : [page, page];
}

const STOP = new Set("the and for are but not you all any can had her was one our out has have this that with from they will what when which their there than then them these those into each also only such some more most other its it's very just like about over under been were your how why who use used uses using does".split(" "));

function words(s: string): Set<string> {
  return new Set((s.toLowerCase().match(/[a-z0-9]{3,}/g) ?? []).filter((w) => !STOP.has(w)));
}

function sharedWords(text: string, target: Set<string>): number {
  let n = 0;
  for (const w of words(text)) if (target.has(w)) n++;
  return n;
}

/**
 * The retrieved passage a verified citation points to, or null if there is none to show.
 *
 * The document must match exactly (ignoring case, spacing and the file extension, or after dropping a section path).
 * With a page, only passages whose pages intersect the cited page or range qualify; if none does, there is no
 * passage rather than a wrong one. Among several candidates, the one sharing most words with the citing sentence wins
 * (the first, which is the most relevant, on a tie).
 */
export function chunkForCitation(c: Pick<CitationCheck, "doc" | "page" | "status"> & { label?: string }, chunks: Chunk[], sentence = ""): number | null {
  if (c.status !== "ok") return null;
  const indexed = chunks.map((ch, i) => [ch, i] as const);
  let sameDocument = indexed.filter(([ch]) => sameKeys(ch.doc, c.doc));
  if (!sameDocument.length) {
    const head = documentPart(c.doc);
    if (head) sameDocument = indexed.filter(([ch]) => sameKeys(ch.doc, head));
  }
  const range = citedPages(c.label, c.page);
  const candidates = range
    ? sameDocument.filter(([ch]) => {
        if (ch.page == null) return false;
        const end = ch.end_page != null && ch.end_page >= ch.page ? ch.end_page : ch.page;
        return ch.page <= range[1] && range[0] <= end;
      })
    : sameDocument;
  if (!candidates.length) return null;
  const target = words(sentence);
  let best = candidates[0]!;
  if (target.size) {
    let bestScore = sharedWords(best[0].text, target);
    for (const cand of candidates.slice(1)) {
      const score = sharedWords(cand[0].text, target);
      if (score > bestScore) {
        best = cand;
        bestScore = score;
      }
    }
  }
  return best[1];
}

function stripMarkdown(s: string): string {
  return s.replace(/[*_`#>~]/g, "").replace(/\s+/g, " ").trim();
}

/** The sentence just before a citation: back to the previous sentence end, line break or citation. */
function citingSentence(before: string): string {
  const cut = Math.max(before.lastIndexOf("\n"), before.search(/[.!?]\s[^.!?]*$/) + 1, before.lastIndexOf("]") + 1);
  return stripMarkdown(before.slice(Math.max(0, cut)).slice(-400));
}

/** The server-checked citations this bracket holds, matched by exact label only. */
function matching(inner: string, byLabel: Map<string, CitationCheck>, chunkDocs: string[]): CitationCheck[] {
  const found: CitationCheck[] = [];
  for (const candidate of [...splitCitations(inner, chunkDocs), inner]) {
    const c = byLabel.get(norm(candidate));
    if (c && !found.includes(c)) found.push(c);
  }
  return found;
}

/** The citations a prose parenthesis holds, and the parts of it that are not citations (kept as text). */
function matchingParen(inner: string, byLabel: Map<string, CitationCheck>, chunkDocs: string[]): { found: CitationCheck[]; rest: string[] } {
  const found: CitationCheck[] = [];
  const rest: string[] = [];
  for (const part of splitCitations(cleanParen(inner), chunkDocs)) {
    const c = byLabel.get(norm(part));
    if (!c) rest.push(part);
    else if (!found.includes(c)) found.push(c);
  }
  return { found, rest };
}

// Marks a citation removed as a duplicate, so the separator before it goes too.
const DROPPED = "\u0000";

/** Two references show the same thing: the same passage, or (with no passage) the same citation. */
const sameTarget = (a: CiteRef, b: CiteRef) => (a.chunk !== null ? a.chunk === b.chunk : b.chunk === null && a.status === b.status && norm(a.label) === norm(b.label));

// An inline code span that holds nothing but one citation, e.g. `[doc.pdf (page 3)]` (some models wrap citations in backticks).
const CODED_CITATION = /^`\s*(\[[^[\]\n]{3,200}\]|\((?:[^()[\]\n]|\([^()[\]\n]*\)){3,300}\))\s*`$/;

/** Removes the backticks around inline code spans that are exactly a known citation, so they become chips too. */
function unwrapCodedCitations(answer: string, byLabel: Map<string, CitationCheck>, chunkDocs: string[]): string {
  return answer
    .split(CODE)
    .map((part, i) => {
      if (i % 2 === 0) return part;
      const m = CODED_CITATION.exec(part);
      const body = m?.[1];
      if (!body) return part;
      const known = body.startsWith("[") ? matching(body.slice(1, -1), byLabel, chunkDocs).length > 0 : matchingParen(body.slice(1, -1), byLabel, chunkDocs).found.length > 0;
      return known ? body : part;
    })
    .join("");
}

export function linkCitations(answer: string, citations: CitationCheck[] | undefined, chunks: Chunk[]): LinkedAnswer {
  const refs: CiteRef[] = [];
  if (!citations?.length) return { markdown: answer, refs };
  const byLabel = new Map<string, CitationCheck>();
  for (const c of citations) if (!byLabel.has(norm(c.label))) byLabel.set(norm(c.label), c);
  const chunkDocs = [...new Set(chunks.map((ch) => ch.doc))];
  const parts = unwrapCodedCitations(answer, byLabel, chunkDocs).split(CODE);
  const markdown = parts
    .map((part, i) => {
      if (i % 2 === 1) return part; // code
      // The chips of the citation just before, while only spaces or punctuation separate it from the next one.
      let previous: CiteRef[] = [];
      let previousEnd = -1;
      const linkedPart = part.replace(CITATION, (whole: string, inner: string | undefined, paren: string | undefined, offset: number) => {
        const { found, rest } = inner !== undefined ? { found: matching(inner, byLabel, chunkDocs), rest: [] } : matchingParen(paren!, byLabel, chunkDocs);
        if (!found.length) return whole;
        const adjacent = previousEnd >= 0 && /^[\s,;]*$/.test(part.slice(previousEnd, offset));
        const sentence = citingSentence(part.slice(0, offset));
        const group: CiteRef[] = [];
        for (const c of found) {
          const ref: CiteRef = { id: refs.length, chunk: chunkForCitation(c, chunks, sentence), label: c.label, doc: c.doc, page: c.page ?? null, status: c.status, sentence };
          if (group.some((g) => sameTarget(g, ref)) || (adjacent && previous.some((g) => sameTarget(g, ref)))) continue; // a duplicate chip
          refs.push(ref);
          group.push(ref);
        }
        previous = adjacent ? [...previous, ...group] : group;
        previousEnd = offset + whole.length;
        const chips = group.map((ref) => `[${ref.id}](${CITE_PREFIX}${ref.id})`).join("");
        if (!group.length && !rest.length) return DROPPED; // every citation here repeats the chip just before it
        return rest.length ? `${chips} (${rest.join("; ")})` : chips;
      });
      return linkedPart.replace(/[\s,;]*\u0000/g, "").replace(WRAPPED_CHIPS, (_whole: string, chips: string) => chips.replace(/[\s,;]+/g, ""));
    })
    .join("");
  return { markdown, refs };
}

/** Where the passage best matches the citing sentence, as character offsets, or null when nothing overlaps enough. */
export function closestSentence(text: string, sentence: string): { start: number; end: number } | null {
  const target = words(sentence);
  if (target.size === 0) return null;
  let best: { start: number; end: number; score: number } | null = null;
  for (const m of text.matchAll(/[^.!?\n]+[.!?]*/g)) {
    const span = m[0];
    const own = words(span);
    let overlap = 0;
    for (const w of own) if (target.has(w)) overlap++;
    if (overlap === 0) continue;
    const score = overlap / Math.sqrt(own.size + 1);
    if (!best || score > best.score) {
      const lead = span.length - span.trimStart().length;
      best = { start: m.index! + lead, end: m.index! + span.trimEnd().length, score };
    }
  }
  if (!best) return null;
  const needed = target.size >= 4 ? 2 : 1;
  const overlap = [...words(text.slice(best.start, best.end))].filter((w) => target.has(w)).length;
  return overlap >= needed ? { start: best.start, end: best.end } : null;
}

/** A short excerpt around the highlight, so long passages open on the part that matters. */
export function excerpt(text: string, focus: { start: number; end: number } | null, radius = 320): { text: string; offset: number; clippedStart: boolean; clippedEnd: boolean } {
  if (text.length <= radius * 2 + 120) return { text, offset: 0, clippedStart: false, clippedEnd: false };
  const centre = focus ? focus.start : 0;
  let start = Math.max(0, centre - radius);
  let end = Math.min(text.length, (focus ? focus.end : 0) + radius);
  if (start > 0) {
    const space = text.indexOf(" ", start);
    start = space >= 0 && space < centre ? space + 1 : start;
  }
  if (end < text.length) {
    const space = text.lastIndexOf(" ", end);
    end = space > (focus?.end ?? 0) ? space : end;
  }
  return { text: text.slice(start, end), offset: start, clippedStart: start > 0, clippedEnd: end < text.length };
}

export const twoDigits = (n: number) => String(n).padStart(2, "0");
