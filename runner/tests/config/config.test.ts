import { test } from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { loadConfig } from "../../src/config.ts";

test("PT_WORKSPACE override sets workspaceRoot and beUploadsDir", () => {
  const cfg = loadConfig({ PT_WORKSPACE: "/tmp/ws" });
  assert.equal(cfg.workspaceRoot, "/tmp/ws");
  assert.equal(cfg.beUploadsDir, join("/tmp/ws", "product-core-backend", "uploads"));
});

test("defaults appUrl to https://plextrac.localhost when env is empty", () => {
  const cfg = loadConfig({});
  assert.equal(cfg.appUrl, "https://plextrac.localhost");
});
