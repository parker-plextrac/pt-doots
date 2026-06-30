import { test } from "node:test";
import assert from "node:assert/strict";
import { renderSummaryMarkdown } from "../../src/report/reporter.ts";

test("renders a FAIL summary with the offending row", () => {
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
  assert.match(md, /Heading Six/);
  assert.match(md, /\b5\b/);
});
