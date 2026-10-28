/** Text out of a file, page by page, entirely in the browser. */

export const MAX_FILE_MB = 100;
export const ACCEPT = ".pdf,.txt,.md";

export class ExtractError extends Error {}

async function pdfPages(file: File, onProgress?: (page: number, total: number) => void): Promise<string[]> {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
  const doc = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
  const pages: string[] = [];
  for (let n = 1; n <= doc.numPages; n++) {
    const content = await (await doc.getPage(n)).getTextContent();
    pages.push(content.items.map((i) => ("str" in i ? i.str + (i.hasEOL ? "\n" : " ") : "")).join(""));
    onProgress?.(n, doc.numPages);
  }
  void doc.cleanup?.();
  return pages;
}

/** Plain text and Markdown have no pages; cut them into page-sized blocks so citations still point somewhere. */
export function textPages(text: string, perPage = 3000): string[] {
  const pages: string[] = [];
  for (let i = 0; i < text.length; i += perPage) pages.push(text.slice(i, i + perPage));
  return pages;
}

export async function extractPages(file: File, onProgress?: (page: number, total: number) => void): Promise<string[]> {
  if (file.size > MAX_FILE_MB * 1024 * 1024) throw new ExtractError(`${file.name} is larger than ${MAX_FILE_MB} MB.`);
  const name = file.name.toLowerCase();
  let pages: string[];
  try {
    pages = name.endsWith(".pdf") ? await pdfPages(file, onProgress) : name.endsWith(".txt") || name.endsWith(".md") ? textPages(await file.text()) : [];
  } catch {
    throw new ExtractError(`Could not read ${file.name}. Is it a valid, unlocked PDF?`);
  }
  if (!name.match(/\.(pdf|txt|md)$/)) throw new ExtractError(`${file.name}: only PDF, TXT and Markdown files work here.`);
  if (pages.every((p) => !p.trim())) throw new ExtractError(`${file.name} has no selectable text (a scanned PDF needs OCR first).`);
  return pages;
}
