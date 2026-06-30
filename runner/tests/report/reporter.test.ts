import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { renderSummaryMarkdown, writeRun } from "../../src/report/reporter.ts";

test("renders a FAIL summary with pinned row columns", () => {
  const md = renderSummaryMarkdown({
    ticketKey: "IO-2294",
    verify: {
      pass: false,
      results: [
        { label: "Heading One", expectedLevel: 0, actualLevel: 0, pass: true },
        { label: "Heading Six", expectedLevel: 5, actualLevel: 0, pass: false },
      ],
    },
  });
  assert.match(md, /FAIL/);
  assert.match(md, /\| Heading Six \| 5 \| 0 \| MISMATCH \|/);
});

test("renders a PASS summary with no MISMATCH rows", () => {
  const md = renderSummaryMarkdown({
    ticketKey: "IO-2294",
    verify: {
      pass: true,
      results: [
        { label: "Heading One", expectedLevel: 0, actualLevel: 0, pass: true },
      ],
    },
  });
  assert.match(md, /PASS/);
  assert.doesNotMatch(md, /MISMATCH/);
});

test("writeRun writes summary.md and result.json to the run dir", () => {
  const dir = mkdtempSync(join(tmpdir(), "writerun-"));
  try {
    const verify = {
      pass: true,
      results: [
        { label: "Heading One", expectedLevel: 0, actualLevel: 0, pass: true },
      ],
    };
    const { summaryPath, resultJsonPath } = writeRun(join(dir, "run"), {
      ticketKey: "IO-2294",
      verify,
    });
    assert.ok(existsSync(summaryPath));
    assert.ok(existsSync(resultJsonPath));
    const parsed: unknown = JSON.parse(readFileSync(resultJsonPath, "utf8"));
    assert.deepEqual(parsed, verify);
  } finally {
    rmSync(dir, { recursive: true });
  }
});

test("escapes pipe characters in heading labels so the markdown table stays valid", () => {
  const md = renderSummaryMarkdown({
    ticketKey: "IO-2294",
    verify: {
      pass: true,
      results: [
        { label: "Heading | One", expectedLevel: 0, actualLevel: 0, pass: true },
      ],
    },
  });
  assert.match(md, /Heading \\\| One/);
});
