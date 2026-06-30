import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseTocRows } from "../../src/verify/debugHtmlParser.ts";

const here = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(here, "..", "fixtures", "debug.html");
const fixtureHtml = readFileSync(fixturePath, "utf8");

describe("parseTocRows — real debug HTML fixture", () => {
  it("returns at least 6 rows from the fixture", () => {
    const rows = parseTocRows(fixtureHtml);
    assert.ok(rows.length >= 6, `expected >= 6 rows, got ${rows.length}`);
  });

  it("every row has a non-empty string label and an integer level 0..5", () => {
    const rows = parseTocRows(fixtureHtml);
    for (const row of rows) {
      assert.equal(typeof row.label, "string");
      assert.ok(row.label.length > 0, "label must be non-empty");
      assert.ok(Number.isInteger(row.level), `level must be integer, got ${row.level}`);
      assert.ok(row.level >= 0 && row.level <= 5, `level out of range: ${row.level}`);
    }
  });

  it("Heading One maps to level 0 (h1)", () => {
    const rows = parseTocRows(fixtureHtml);
    const row = rows.find((r) => r.label === "Heading One");
    assert.ok(row !== undefined, "Heading One not found in rows");
    assert.equal(row.level, 0);
  });

  it("Heading Two maps to level 1 (h2)", () => {
    const rows = parseTocRows(fixtureHtml);
    const row = rows.find((r) => r.label === "Heading Two");
    assert.ok(row !== undefined, "Heading Two not found in rows");
    assert.equal(row.level, 1);
  });

  it("Heading Three maps to level 2 (h3)", () => {
    const rows = parseTocRows(fixtureHtml);
    const row = rows.find((r) => r.label === "Heading Three");
    assert.ok(row !== undefined, "Heading Three not found in rows");
    assert.equal(row.level, 2);
  });

  it("Heading Four maps to level 3 (h4)", () => {
    const rows = parseTocRows(fixtureHtml);
    const row = rows.find((r) => r.label === "Heading Four");
    assert.ok(row !== undefined, "Heading Four not found in rows");
    assert.equal(row.level, 3);
  });

  it("Heading Five maps to level 4 (h5)", () => {
    const rows = parseTocRows(fixtureHtml);
    const row = rows.find((r) => r.label === "Heading Five");
    assert.ok(row !== undefined, "Heading Five not found in rows");
    assert.equal(row.level, 4);
  });

  it("Heading Six maps to level 5 (h6)", () => {
    const rows = parseTocRows(fixtureHtml);
    const row = rows.find((r) => r.label === "Heading Six");
    assert.ok(row !== undefined, "Heading Six not found in rows");
    assert.equal(row.level, 5);
  });
});
