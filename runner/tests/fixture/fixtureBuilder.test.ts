import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildPtrac } from "../../src/fixture/fixtureBuilder.ts";
import { isRecord } from "../../src/util/guards.ts";

test("buildPtrac writes a valid ptrac with narrative HTML at the correct path", () => {
  const { path } = buildPtrac(
    { sectionTitle: "Heading Levels", narrativeHtml: "<h1>Heading One</h1><h6>Heading Six</h6>" },
    "IO-2294",
    "unit",
  );

  const parsed: unknown = JSON.parse(readFileSync(path, "utf8"));
  if (!isRecord(parsed)) throw new Error("ptrac is not an object");

  const reportInfo = parsed["report_info"];
  if (!isRecord(reportInfo)) throw new Error("missing report_info");

  const execSummary = reportInfo["exec_summary"];
  if (!isRecord(execSummary)) throw new Error("missing exec_summary");

  const customFields = execSummary["custom_fields"];
  if (!Array.isArray(customFields)) throw new Error("custom_fields is not an array");

  const section = customFields[0];
  if (!isRecord(section)) throw new Error("no sections in custom_fields");

  const text = section["text"];
  assert.ok(typeof text === "string", "text field is a string");
  assert.ok(text.includes("<h1>Heading One</h1>"), "h1 present in narrative text");
  assert.ok(text.includes("<h6>Heading Six</h6>"), "h6 present in narrative text");
});
