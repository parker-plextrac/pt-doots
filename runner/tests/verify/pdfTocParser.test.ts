// Offline unit test for pdfTocParser.ts against a committed PDF fixture.
//
// The fixture (tests/fixtures/sample-export.pdf) is a real PDF export produced
// by the fix branch of the export service with a deep-level ToC template.
// It contains dummy heading content with no customer data.
//
// These tests answer the question: can the parser read a real rendered ToC?
// If the parser returns zero entries the second test is unreachable and the
// first will hard-fail — that result is reported as-is, not papered over.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import {
  parseTocFromPdf,
  readPage1Items,
  extractTocEntries,
} from "../../src/verify/pdfTocParser.ts";

const fixturePath = fileURLToPath(
  new URL("../fixtures/sample-export.pdf", import.meta.url),
);

describe("pdfTocParser — real sample PDF", () => {
  it("extracts at least one ToC entry, each with visible text and an x-coordinate", async () => {
    const items = await readPage1Items(fixturePath);
    const entries = extractTocEntries(items);
    assert.ok(
      entries.length >= 1,
      `expected at least one ToC entry, got ${entries.length}`,
    );
    for (const entry of entries) {
      assert.ok(
        entry.str.trim().length > 0,
        `entry at x=${entry.x} has empty text`,
      );
      assert.ok(
        Number.isFinite(entry.x),
        `entry "${entry.str}" has non-finite x-coordinate: ${entry.x}`,
      );
    }
  });

  it("derives at least two distinct heading levels from x-indents", async () => {
    const rows = await parseTocFromPdf(fixturePath);
    assert.ok(rows.length >= 1, `expected at least one row, got ${rows.length}`);
    const distinctLevels = new Set(rows.map((r) => r.level));
    assert.ok(
      distinctLevels.size >= 2,
      `expected at least 2 distinct levels, got ${distinctLevels.size}: ${[...distinctLevels].join(", ")}`,
    );
  });
});
