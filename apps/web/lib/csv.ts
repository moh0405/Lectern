/**
 * CSV cell, RFC 4180 quoting. Cells starting with = + - @ (or tab/CR) are prefixed with an apostrophe
 * so a spreadsheet will not run text such as "=HYPERLINK(...)" as a formula.
 */
export function csvCell(value: unknown): string {
  let s = value === null || value === undefined ? "" : String(value);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsvRows(rows: unknown[][]): string {
  return rows.map((r) => r.map(csvCell).join(",")).join("\n") + "\n";
}
