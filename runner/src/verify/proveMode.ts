// --prove mode orchestration for IO-2294 regression harness.
//
// After the normal export run completes (fix branch, real async worker),
// --prove mode additionally:
//   1. Runs the two-pass WeasyPrint simulation on the fix branch.
//   2. git-switches the export repo to main.
//   3. Runs the two-pass WeasyPrint simulation on main.
//   4. git-switches back to the fix branch.
//   5. Compares verifyToc results: expects fix PASS, main FAIL.
//
// The direct simulation is used for both branches so that:
//   a. Fix and main results are produced by the same code path (apples-to-apples).
//   b. The async worker SIGSEGV on main (a separate bug) doesn't block the test.
//
// Callers get back a ProveResult that the CLI renders in the summary.

import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import type { TestSpec } from "../spec/testSpec.ts";
import { verifyToc, type VerifyResult } from "./diff.ts";
import { parseTocFromPdf } from "./pdfTocParser.ts";

export interface ProveResult {
  // Verification result for the fix branch (simulation).
  fix: VerifyResult;
  // Verification result for the main branch (simulation).
  main: VerifyResult;
  // True when fix passes AND main fails — the harness discriminates correctly.
  discriminates: boolean;
}

// Calls simulate_toc.py to produce a PDF from the debug HTML.
// Returns the output PDF path on success, throws on failure.
function runSimulation(
  exportRepoPath: string,
  debugHtmlPath: string,
  outPdfPath: string,
): void {
  const here = new URL(".", import.meta.url).pathname;
  const scriptPath = join(here, "..", "..", "..", "scripts", "simulate_toc.py");

  const result = spawnSync(
    "python3",
    [
      scriptPath,
      "--export-repo", exportRepoPath,
      "--debug-html", debugHtmlPath,
      "--out-pdf", outPdfPath,
    ],
    { encoding: "utf8" },
  );

  if (result.error !== undefined) {
    throw new Error(`simulate_toc.py spawn failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    const stderr = result.stderr ?? "";
    throw new Error(
      `simulate_toc.py exited ${result.status ?? "null"}:\n${stderr.trim()}`,
    );
  }
}

// Switches the export repo to the given branch using `git switch`.
// Throws if the switch fails (branch does not exist, or dirty working tree).
function gitSwitch(exportRepoPath: string, branch: string): void {
  const result = spawnSync("git", ["switch", branch], {
    cwd: exportRepoPath,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(
      `git switch ${branch} failed in ${exportRepoPath}:\n${(result.stderr ?? "").trim()}`,
    );
  }
}

// Returns the currently-checked-out branch name in exportRepoPath.
function currentBranch(exportRepoPath: string): string {
  const result = spawnSync("git", ["branch", "--show-current"], {
    cwd: exportRepoPath,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(
      `git branch --show-current failed in ${exportRepoPath}:\n${(result.stderr ?? "").trim()}`,
    );
  }
  return (result.stdout ?? "").trim();
}

export async function runProveMode(
  spec: TestSpec,
  debugHtmlPath: string,
  exportRepoPath: string,
  fixBranchName: string,
  runDir: string,
): Promise<ProveResult> {
  const originalBranch = currentBranch(exportRepoPath);

  // Ensure we start on the fix branch.
  if (originalBranch !== fixBranchName) {
    throw new Error(
      `--prove requires the export repo to be on the fix branch (${fixBranchName}), ` +
        `but it is on '${originalBranch}'.  Switch manually before running.`,
    );
  }

  const fixPdfPath = join(runDir, "prove-fix.pdf");
  const mainPdfPath = join(runDir, "prove-main.pdf");

  // --- Simulation on fix branch (already checked out) ---
  console.log("  [prove] simulating fix branch…");
  runSimulation(exportRepoPath, debugHtmlPath, fixPdfPath);
  const fixRows = await parseTocFromPdf(fixPdfPath);
  const fixVerify = verifyToc(spec, fixRows);

  // --- Switch to main for main simulation ---
  console.log("  [prove] switching export repo to main…");
  gitSwitch(exportRepoPath, "main");

  let mainVerify: VerifyResult;
  let mainRows;
  try {
    console.log("  [prove] simulating main branch…");
    runSimulation(exportRepoPath, debugHtmlPath, mainPdfPath);
    mainRows = await parseTocFromPdf(mainPdfPath);
    mainVerify = verifyToc(spec, mainRows);
  } finally {
    // Always restore the fix branch, even if simulation or parsing throws.
    console.log(`  [prove] restoring ${fixBranchName}…`);
    gitSwitch(exportRepoPath, fixBranchName);
  }

  return {
    fix: fixVerify,
    main: mainVerify,
    discriminates: fixVerify.pass && !mainVerify.pass,
  };
}
