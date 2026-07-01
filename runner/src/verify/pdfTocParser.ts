// PDF-based Table of Contents extractor for IO-2294 regression harness.
//
// Reads the FINAL PDF produced by the export service and extracts ToC entries
// by measuring x-coordinates on the ToC page.  Each level of indentation adds
// 0.25 in (18 pt in PDF coordinates) — the same step that the CSS rule
// `text-indent: 0.25in` per level produces.
//
// Algorithm:
//   1. Read page 1 text items (the io-2294-toc-probe template guarantees ToC
//      is on page 1 — no cover page).
//   2. Group items by y-row (2 pt tolerance to absorb sub-pixel variation).
//   3. A row that has BOTH a label (x < TOC_SPLIT_X) AND a page number
//      (x >= TOC_SPLIT_X) is a ToC entry.  Rows without a page number are
//      either the "Table of Contents" header or content headings that spilled
//      onto page 1 — both are ignored.
//   4. Calibrate: x_base = minimum label-x across all ToC entries.
//      step = minimum positive difference between distinct x values, or
//      DEFAULT_LEVEL_STEP_PT if all entries are at the same x.
//   5. level = round((x - x_base) / step) for each entry.
//
// The result is deterministic and noise-free: empirical measurements on the
// probe template show exact integer multiples of 18 pt between levels with
// zero floating-point scatter after rounding.

import { readFileSync } from "node:fs";
import type { TocRow } from "./types.ts";

// x-split: labels appear left of this threshold; page numbers appear right.
// 300 pt leaves wide margin even for deeply indented entries (level-3 = 0.75 in
// ≈ 54 pt above the 1 in left margin base ≈ 72 pt, so max label x ≈ 126 pt).
const TOC_SPLIT_X = 300;

// CSS `text-indent: 0.25in` in PDF points = 0.25 * 72 = 18 pt per level.
const DEFAULT_LEVEL_STEP_PT = 18;

interface TextItem {
  str: string;
  x: number;
  y: number;
}

// Rounds y to the nearest 2 pt so items on the same typographic line
// (which may differ by < 1 pt due to baseline shifts) map to the same key.
function yKey(y: number): number {
  return Math.round(y / 2) * 2;
}

function isPageNumber(str: string): boolean {
  return /^\d+$/.test(str);
}

async function readPage1Items(pdfPath: string): Promise<TextItem[]> {
  // Dynamic import keeps pdfjs off the main module graph for tests that
  // do not exercise the PDF path.
  const { getDocument } = await import(
    "pdfjs-dist/legacy/build/pdf.mjs" as string
  );
  const data = new Uint8Array(readFileSync(pdfPath));
  const loadingTask = getDocument({ data, verbosity: 0 });
  const pdf = await loadingTask.promise;
  const page = await pdf.getPage(1);
  const content = await page.getTextContent();
  return (content.items as Array<{ str: string; transform: number[] }>)
    .map((item) => ({
      str: item.str.trim(),
      x: Math.round(item.transform[4] ?? 0),
      y: Math.round(item.transform[5] ?? 0),
    }))
    .filter((item) => item.str.length > 0);
}

function extractTocEntries(items: TextItem[]): TextItem[] {
  // Group by y-row
  const byY = new Map<number, TextItem[]>();
  for (const item of items) {
    const key = yKey(item.y);
    if (!byY.has(key)) byY.set(key, []);
    byY.get(key)!.push(item);
  }

  const entries: TextItem[] = [];
  for (const rowItems of byY.values()) {
    const label = rowItems.find(
      (i) => i.x < TOC_SPLIT_X && !isPageNumber(i.str),
    );
    const hasPageNum = rowItems.some(
      (i) => i.x >= TOC_SPLIT_X || isPageNumber(i.str),
    );
    // Only rows with both a label and a page number are ToC entries.
    if (label !== undefined && hasPageNum) {
      entries.push(label);
    }
  }

  // Sort top-to-bottom by descending y (PDF y-axis is bottom-up)
  entries.sort((a, b) => b.y - a.y);
  return entries;
}

function calibrateStep(xValues: number[]): { xBase: number; step: number } {
  const distinct = [...new Set(xValues)].sort((a, b) => a - b);
  const xBase = distinct[0] ?? 0;

  if (distinct.length < 2) {
    return { xBase, step: DEFAULT_LEVEL_STEP_PT };
  }

  // Minimum gap between consecutive distinct x values = one level step.
  let minGap = Infinity;
  for (let i = 1; i < distinct.length; i++) {
    const gap = (distinct[i] ?? 0) - (distinct[i - 1] ?? 0);
    if (gap > 0 && gap < minGap) minGap = gap;
  }
  return { xBase, step: minGap === Infinity ? DEFAULT_LEVEL_STEP_PT : minGap };
}

// Exported for unit testing of the pure calibration logic.
export { calibrateStep, extractTocEntries, readPage1Items };
export type { TextItem };

// Main entry point: returns TocRow[] with level derived from x-coordinate.
export async function parseTocFromPdf(pdfPath: string): Promise<TocRow[]> {
  const items = await readPage1Items(pdfPath);
  const entries = extractTocEntries(items);

  const { xBase, step } = calibrateStep(entries.map((e) => e.x));

  return entries.map((entry) => ({
    label: entry.str,
    level: Math.round((entry.x - xBase) / step),
  }));
}
