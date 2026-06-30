import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

export interface HarnessConfig {
  appUrl: string;
  username: string;
  password: string;
  beUploadsDir: string;
  workspaceRoot: string;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): HarnessConfig {
  // This file lives at <workspace>/<repo>/runner/src/config.ts, so three levels
  // up is the workspace root that holds the product repos. PT_WORKSPACE overrides.
  const here = dirname(fileURLToPath(import.meta.url));
  const workspaceRoot = env.PT_WORKSPACE ?? join(here, "..", "..", "..");
  return {
    appUrl: env.PT_APP_URL ?? "https://plextrac.localhost",
    username: env.PT_TEST_USER ?? "global_admin",
    password: env.PT_TEST_PASS ?? "password",
    beUploadsDir: env.PT_BE_UPLOADS ?? join(workspaceRoot, "product-core-backend", "uploads"),
    workspaceRoot,
  };
}
