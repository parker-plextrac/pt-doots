import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { TestSpecSchema, loadSpec } from "../../src/spec/testSpec.ts";

const valid = {
  ticketKey: "IO-2294",
  reproContent: {
    sectionTitle: "Heading Levels",
    narrativeHtml: "<h1>Heading One</h1><h2>Heading Two</h2>",
  },
  expectedAssertions: [
    { label: "Heading One", expectedLevel: 0 },
    { label: "Heading Two", expectedLevel: 1 },
  ],
};

test("accepts a well-formed spec", () => {
  assert.doesNotThrow(() => TestSpecSchema.parse(valid));
  assert.deepEqual(TestSpecSchema.parse(valid), valid);
});

test("rejects a bad ticket key", () => {
  assert.throws(() => TestSpecSchema.parse({ ...valid, ticketKey: "nope" }));
});

test("rejects empty expectedAssertions", () => {
  assert.throws(() => TestSpecSchema.parse({ ...valid, expectedAssertions: [] }));
});

test("rejects unknown top-level keys", () => {
  assert.throws(() => TestSpecSchema.parse({ ...valid, extra: true }));
});

test("loadSpec round-trips a valid spec file", () => {
  const dir = mkdtempSync(join(tmpdir(), "testspec-"));
  const file = join(dir, "spec.json");
  try {
    writeFileSync(file, JSON.stringify(valid));
    assert.deepEqual(loadSpec(file), valid);
  } finally {
    rmSync(dir, { recursive: true });
  }
});

test("loadSpec throws with path context on invalid JSON", () => {
  const dir = mkdtempSync(join(tmpdir(), "testspec-"));
  const file = join(dir, "spec.json");
  try {
    writeFileSync(file, "{ not json");
    assert.throws(() => loadSpec(file), /Invalid JSON in TestSpec/);
  } finally {
    rmSync(dir, { recursive: true });
  }
});
