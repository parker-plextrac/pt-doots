import { test } from "node:test";
import assert from "node:assert/strict";
import { verifyToc } from "../../src/verify/diff.ts";
import type { TestSpec } from "../../src/spec/testSpec.ts";

const spec: TestSpec = {
  ticketKey: "IO-2294",
  reproContent: { sectionTitle: "x", narrativeHtml: "x" },
  expectedAssertions: [
    { label: "Heading One", expectedLevel: 0 },
    { label: "Heading Six", expectedLevel: 5 },
  ],
};

test("passes when every heading maps to its expected level", () => {
  const r = verifyToc(spec, [
    { label: "Heading One", level: 0 },
    { label: "Heading Six", level: 5 },
  ]);
  assert.ok(r.pass);
});

test("fails and flags the deep heading when levels collapse", () => {
  const r = verifyToc(spec, [
    { label: "Heading One", level: 0 },
    { label: "Heading Six", level: 0 },
  ]);
  assert.equal(r.pass, false);
  assert.equal(r.results.find((x) => x.label === "Heading Six")?.actualLevel, 0);
});

test("missing heading is a fail with null actual", () => {
  const r = verifyToc(spec, [{ label: "Heading One", level: 0 }]);
  assert.equal(r.pass, false);
  assert.equal(r.results.find((x) => x.label === "Heading Six")?.actualLevel, null);
});

test("extra rows not in expectedAssertions are ignored and pass stays true", () => {
  const r = verifyToc(spec, [
    { label: "Heading One", level: 0 },
    { label: "Heading Six", level: 5 },
    { label: "Heading Not In Spec", level: 3 },
  ]);
  assert.ok(r.pass);
  assert.equal(r.results.length, 2);
});
