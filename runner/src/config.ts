import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

export interface HarnessConfig {
  appUrl: string;
  username: string;
  password: string;
  beUploadsDir: string;
  workspaceRoot: string;
  // Absolute path to the product-services-export checkout.
  // Required by --prove mode to run the two-pass WeasyPrint simulation.
  exportRepoPath: string;
  // Filename (not path) for the temporary PDF template placed in
  // {beUploadsDir}/export_templates/temp/ before each export run.
  // The async export API resolves it via ?temporaryTemplateName=<this>.
  probeTemplateName: string;
  // Fix branch name in the export repo, used by --prove to restore state.
  exportFixBranch: string;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): HarnessConfig {
  // This file lives at <workspace>/<repo>/runner/src/config.ts, so three levels
  // up is the workspace root that holds the product repos. PT_WORKSPACE overrides.
  const here = dirname(fileURLToPath(import.meta.url));
  const workspaceRoot = env["PT_WORKSPACE"] ?? join(here, "..", "..", "..");
  return {
    appUrl: env["PT_APP_URL"] ?? "https://plextrac.localhost",
    username: env["PT_TEST_USER"] ?? "global_admin",
    password: env["PT_TEST_PASS"] ?? "password",
    beUploadsDir: env["PT_BE_UPLOADS"] ?? join(workspaceRoot, "product-core-backend", "uploads"),
    workspaceRoot,
    exportRepoPath:
      env["PT_EXPORT_REPO"] ?? join(workspaceRoot, "product-services-export"),
    probeTemplateName:
      env["PT_PROBE_TEMPLATE_NAME"] ?? "tenant_0_export_io2294toc.j2",
    exportFixBranch:
      env["PT_EXPORT_FIX_BRANCH"] ?? "IO-2294-pdf-toc-heading-levels",
  };
}
