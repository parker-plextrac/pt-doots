// Parses the debug HTML written by the PDF export pipeline when the
// PDF_EXPORT_DEBUG_HTML_FILE feature flag is on.
//
// Real structure discovered from live exports (not table-of-contents-line-item-row
// elements as the CSS rules suggest — those CSS rules exist in the template but
// NO corresponding HTML elements are rendered for basic narrative-only reports):
//
//   Section headings:  <h1 class="page-break-before" id="...">Section Name</h1>
//   Narrative content: <h1><a id="heading-slug">Heading One</a></h1>
//                      <h2><a id="heading-slug">Heading Two</a></h2>  ...
//
// Level mapping: h1 → 0, h2 → 1, h3 → 2, h4 → 3, h5 → 4, h6 → 5
// (mirrors the table-of-contents-line-item.level-N CSS comment "TOC LEVEL N+1")
//
// Debug HTML filename pattern (async export):
//   export_{clientId}_{reportId}_{jobId}.html
import { load } from "cheerio";
import { readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import type { TocRow } from "./types.ts";

export function parseTocRows(html: string): TocRow[] {
  const $ = load(html);
  const rows: TocRow[] = [];

  $("h1, h2, h3, h4, h5, h6").each((_i, el) => {
    const tagName = $(el).prop("tagName");
    if (typeof tagName !== "string") return;
    const match = tagName.toLowerCase().match(/^h([1-6])$/);
    if (match === null) return;
    const levelStr = match[1];
    if (levelStr === undefined) return;
    const level = parseInt(levelStr, 10) - 1;
    const label = $(el).text().trim();
    if (label.length > 0) {
      rows.push({ label, level });
    }
  });

  return rows;
}

// Returns the path to the most recent debug HTML for the given client/report.
// Pattern: export_{clientId}_{reportId}*.html (covers both 2-part legacy and
// 3-part async-export filenames).
export function findLatestDebugHtml(
  dir: string,
  clientId: string,
  reportId: string,
): string {
  const prefix = `export_${clientId}_${reportId}`;
  const suffix = ".html";
  const entries = readdirSync(dir);
  const matching = entries.filter(
    (name) => name.startsWith(prefix) && name.endsWith(suffix),
  );
  if (matching.length === 0) {
    throw new Error(
      `No debug HTML found in ${dir} matching export_${clientId}_${reportId}*.html\n` +
        `Ensure the PDF_EXPORT_DEBUG_HTML_FILE feature flag is on and the export completed.`,
    );
  }
  // Sort newest-first by mtime
  matching.sort((a, b) => {
    const aMtime = statSync(join(dir, a)).mtimeMs;
    const bMtime = statSync(join(dir, b)).mtimeMs;
    return bMtime - aMtime;
  });
  const chosen = matching[0];
  if (chosen === undefined) {
    throw new Error("Internal: matching[0] unexpectedly undefined");
  }
  return join(dir, chosen);
}
