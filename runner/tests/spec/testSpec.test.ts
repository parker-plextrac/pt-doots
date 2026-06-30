import { test } from "node:test";
import assert from "node:assert/strict";
import { TestSpecSchema } from "../../src/spec/testSpec.ts";

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
  assert.equal(TestSpecSchema.parse(valid).ticketKey, "IO-2294");
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
