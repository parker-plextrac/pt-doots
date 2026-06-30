import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { evaluateFlags } from "../../src/preflight/preflight.ts";
import { isRecord } from "../../src/util/guards.ts";

const here = dirname(fileURLToPath(import.meta.url));
const raw: unknown = JSON.parse(
  readFileSync(join(here, "../fixtures/featureFlags.json"), "utf8"),
);
if (!isRecord(raw)) {
  throw new Error("featureFlags fixture is not a Record");
}
const fixture: Record<string, unknown> = raw;

test("production fixture passes preflight cleanly", () => {
  const r = evaluateFlags(fixture);
  assert.equal(r.debugHtmlOn, true);
  assert.equal(r.asyncExport, true);
  assert.equal(r.ctfMode, false);
  assert.equal(r.rapidTemplating, false);
  assert.equal(r.blockers.length, 0);
});

test("CTF_MODE on triggers a CTF_MODE blocker", () => {
  const modified: Record<string, unknown> = Object.assign({}, fixture);
  const ctfEntry = fixture["CTF_MODE"];
  if (isRecord(ctfEntry)) {
    modified["CTF_MODE"] = { ...ctfEntry, variation: true };
  }
  const r = evaluateFlags(modified);
  assert.equal(r.ctfMode, true);
  assert.ok(r.blockers.some((b) => b.includes("CTF_MODE")));
});

test("absent PDF_EXPORT_DEBUG_HTML_FILE triggers a debug-HTML blocker", () => {
  const modified: Record<string, unknown> = Object.assign({}, fixture);
  delete modified["PDF_EXPORT_DEBUG_HTML_FILE"];
  const r = evaluateFlags(modified);
  assert.equal(r.debugHtmlOn, false);
  assert.ok(r.blockers.some((b) => b.includes("PDF_EXPORT_DEBUG_HTML_FILE")));
});
