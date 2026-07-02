// Two-pass discrimination proof for export regressions.
//
// runProve() orchestrates:
//   Pass 1 (fix branch)  — runs the full UI export flow on the current branch;
//                          expects PASS.
//   Pass 2 (main)        — switches the export repo to main, reruns the same
//                          flow, expects FAIL (wrong level OR crash/Export-Failed).
//   Restore              — switches the export repo back to the original branch
//                          unconditionally in a finally block, even if pass 2
//                          crashed.
//
// Exit criterion: discriminates = fix.pass && !main.pass
//   A main-side crash or "Export Failed" (no PDF) counts as !main.pass.
//
// Git operations use execFileSync (no shell — no argument injection risk).
// Branch switches are announced to stdout so runs are auditable.
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { HarnessConfig } from "../config.ts";
import type { TestSpec } from "../spec/testSpec.ts";
import { buildPtrac } from "../fixture/fixtureBuilder.ts";
import { runBrowserExport } from "../browser/run.ts";
import { parseTocFromPdf } from "../verify/pdfTocParser.ts";
import { verifyToc } from "../verify/diff.ts";
import type { VerifyResult } from "../verify/diff.ts";
import type { TocRow } from "../verify/types.ts";

// ─── Result types ────────────────────────────────────────────────────────────

export interface ProveRunResult {
  /** Name of the export-repo git branch active during this pass. */
  branch: string;
  /** true = all spec assertions matched; false = mismatch or crash. */
  pass: boolean;
  /** ToC rows extracted from the downloaded PDF (empty on crash). */
  tocRows: TocRow[];
  /** Non-null when the UI export flow threw (crash or Export-Failed). */
  crashMessage: string | null;
  /** null when the pass crashed before producing a PDF. */
  verify: VerifyResult | null;
}

export interface ProveResult {
  fix: ProveRunResult;
  main: ProveRunResult;
  /** true only when fix PASSED and main FAILED — the harness discriminates. */
  discriminates: boolean;
}

// ─── Git helpers ─────────────────────────────────────────────────────────────

function gitCurrentBranch(repoPath: string): string {
  return execFileSync(
    "git",
    ["-C", repoPath, "rev-parse", "--abbrev-ref", "HEAD"],
    { encoding: "utf8" },
  ).trim();
}

function gitSwitch(repoPath: string, branch: string): void {
  execFileSync("git", ["-C", repoPath, "switch", branch], { encoding: "utf8" });
}

// ─── Single-pass runner ───────────────────────────────────────────────────────

// Runs one full UI export cycle.  Catches all errors so that a crash on the
// main side is recorded as pass=false rather than propagating up past the
// unconditional restore in the finally block.
async function runSinglePass(
  cfg: HarnessConfig,
  spec: TestSpec,
  branch: string,
  runId: string,
  templatePath: string,
): Promise<ProveRunResult> {
  try {
    const { path: ptracPath } = buildPtrac(spec.reproContent, spec.ticketKey, runId);
    const { pdfPath } = await runBrowserExport(
      cfg,
      spec.ticketKey,
      runId,
      ptracPath,
      templatePath,
    );
    const tocRows = await parseTocFromPdf(pdfPath);
    const verify = verifyToc(spec, tocRows);
    return { branch, pass: verify.pass, tocRows, crashMessage: null, verify };
  } catch (err) {
    const crashMessage = err instanceof Error ? err.message : String(err);
    return { branch, pass: false, tocRows: [], crashMessage, verify: null };
  }
}

// ─── Console output ───────────────────────────────────────────────────────────

export function logProveRunResult(label: string, result: ProveRunResult): void {
  if (result.crashMessage !== null) {
    console.log(`[prove] ${label}: CRASHED — ${result.crashMessage}`);
    return;
  }
  const status = result.pass ? "PASS" : "FAIL";
  console.log(`[prove] ${label}: ${status}`);
  for (const row of result.tocRows) {
    console.log(`  level ${row.level}: "${row.label}"`);
  }
  if (result.verify !== null) {
    for (const r of result.verify.results) {
      const mark = r.pass ? "ok" : "MISMATCH";
      const actual = r.actualLevel !== null ? String(r.actualLevel) : "missing";
      console.log(
        `  assertion: "${r.label}" expected=${r.expectedLevel} actual=${actual} [${mark}]`,
      );
    }
  }
}

// ─── Main-side pass with unconditional branch restore ────────────────────────

// Separated into its own function so the try/finally always pairs a
// completed pass-1 switch with a pass-2 restore, without leaving the
// 'main' variable potentially unassigned in the outer scope.
async function runMainSideWithRestore(
  cfg: HarnessConfig,
  spec: TestSpec,
  exportRepoPath: string,
  originalBranch: string,
  templatePath: string,
): Promise<ProveRunResult> {
  const runId = `prove-main-${Date.now()}`;
  try {
    console.log("\n[prove] Pass 2 (main): running export ...");
    const result = await runSinglePass(cfg, spec, "main", runId, templatePath);
    logProveRunResult("main", result);
    return result;
  } finally {
    // Unconditional restore — runs even when runSinglePass caught a crash.
    console.log(`\n[prove] Restoring export repo to ${originalBranch} ...`);
    gitSwitch(exportRepoPath, originalBranch);
    console.log(`[prove] Restored to: ${gitCurrentBranch(exportRepoPath)}`);
  }
}

// ─── Public API ───────────────────────────────────────────────────────────────

// Assumes the export repo is already on the fix branch when called.
// Switches to main for pass 2 and always restores the original branch.
export async function runProve(
  cfg: HarnessConfig,
  spec: TestSpec,
): Promise<ProveResult> {
  // prove.ts lives at runner/src/prove/ — fixtures dir is two levels up.
  const here = dirname(fileURLToPath(import.meta.url));
  const templatePath = join(here, "..", "..", "fixtures", "deep-toc-export-template.j2");

  const exportRepoPath = cfg.exportRepoPath;
  const originalBranch = gitCurrentBranch(exportRepoPath);
  console.log(`[prove] Export repo starting on branch: ${originalBranch}`);

  // Pass 1: fix side — run on the current (fix) branch; no switch needed.
  const fixRunId = `prove-fix-${Date.now()}`;
  console.log(`\n[prove] Pass 1 (${originalBranch}): running export ...`);
  const fix = await runSinglePass(cfg, spec, originalBranch, fixRunId, templatePath);
  logProveRunResult("fix", fix);

  // Switch to main for pass 2.
  // If this switch fails (dirty tree, missing branch), the error propagates;
  // no restore is needed because the branch has not changed.
  console.log(`\n[prove] Switching export repo to main ...`);
  gitSwitch(exportRepoPath, "main");
  console.log(`[prove] Now on: ${gitCurrentBranch(exportRepoPath)}`);

  // Pass 2: main side with unconditional restore in finally.
  // runMainSideWithRestore never lets a crash propagate past the finally block.
  const main = await runMainSideWithRestore(
    cfg,
    spec,
    exportRepoPath,
    originalBranch,
    templatePath,
  );

  const discriminates = fix.pass && !main.pass;
  return { fix, main, discriminates };
}
