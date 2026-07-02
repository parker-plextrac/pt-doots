// Entry point: npx tsx src/cli.ts --spec <path> [--headed] [--prove]
//
// Default pipeline (--spec only):
//   loadConfig → loadSpec → authenticate → runPreflight
//   → buildPtrac (generate .ptrac fixture from spec)
//   → runBrowserExport (full UI: create client, import, export, download)
//   → parseTocFromPdf → verifyToc → writeRun → print summary
//   → exit 0 (PASS) / exit 1 (FAIL)
//
// Prove pipeline (--spec + --prove):
//   loadConfig → loadSpec → authenticate → runPreflight
//   → runProve: pass 1 on fix branch (expect PASS) →
//               git switch export repo to main →
//               pass 2 on main (expect FAIL or crash) →
//               git restore export repo (unconditional finally) →
//               assert fix.pass && !main.pass
//   → exit 0 (discriminates) / exit 1 (does not)
import { argv, exit } from "node:process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { loadConfig } from "./config.ts";
import { loadSpec } from "./spec/testSpec.ts";
import { PlexTracApi } from "./api/client.ts";
import { runPreflight } from "./preflight/preflight.ts";
import { buildPtrac } from "./fixture/fixtureBuilder.ts";
import { runBrowserExport } from "./browser/run.ts";
import { parseTocFromPdf } from "./verify/pdfTocParser.ts";
import { verifyToc } from "./verify/diff.ts";
import { writeRun, renderSummaryMarkdown } from "./report/reporter.ts";
import { runProve } from "./prove/prove.ts";
import type { ProveResult } from "./prove/prove.ts";

interface CliArgs {
  specPath: string;
  headed: boolean;
  prove: boolean;
}

function parseArgs(args: readonly string[]): CliArgs {
  let specPath: string | undefined;
  let headed = false;
  let prove = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--spec") {
      const next = args[i + 1];
      if (typeof next !== "string" || next.startsWith("--")) {
        console.error("Error: --spec requires a file path argument");
        exit(1);
      }
      specPath = next;
      i++;
    } else if (arg === "--headed") {
      headed = true;
    } else if (arg === "--prove") {
      prove = true;
    } else if (arg !== undefined && arg.startsWith("--")) {
      console.error(`Unknown option: ${arg}`);
      exit(1);
    }
  }

  if (specPath === undefined) {
    console.error("Usage: cli.ts --spec <path> [--headed] [--prove]");
    exit(1);
  }

  return { specPath, headed, prove };
}

function renderProveResult(result: ProveResult, ticketKey: string): void {
  console.log(`\n${"─".repeat(60)}`);
  console.log(`${ticketKey} --prove result`);
  console.log("─".repeat(60));
  console.log(`  fix side (${result.fix.branch}): ${result.fix.pass ? "PASS" : "FAIL"}`);
  console.log(`  main side: ${result.main.pass ? "PASS" : result.main.crashMessage !== null ? "CRASHED" : "FAIL"}`);
  if (result.main.crashMessage !== null) {
    console.log(`  main crash: ${result.main.crashMessage}`);
  }
  console.log(`  discriminates: ${result.discriminates ? "YES — harness proved fix vs bug" : "NO — check results above"}`);
  console.log("─".repeat(60));
}

async function main(): Promise<void> {
  const { specPath, headed, prove } = parseArgs(argv.slice(2));

  if (headed) {
    process.env["PT_HEADLESS"] = "false";
  }

  const cfg = loadConfig(process.env);
  const spec = loadSpec(specPath);
  const runId = String(Date.now());

  // runDir must match the derivation in run.ts (runner/.runs/{key}-{runId}/)
  const here = dirname(fileURLToPath(import.meta.url));
  const runDir = join(here, "..", ".runs", `${spec.ticketKey}-${runId}`);

  // API client — used only for the read-only feature-flag preflight check.
  const api = new PlexTracApi(cfg);
  await api.authenticate();

  // Preflight: check feature flags; block on CTF_MODE; warn on others.
  const preflight = await runPreflight(api);
  if (preflight.blockers.length > 0) {
    console.error("\nPreflight blockers:");
    for (const b of preflight.blockers) {
      console.error(`  - ${b}`);
    }
    exit(1);
  }

  // --prove mode: two-pass discrimination run (fix branch vs main).
  // Runs the full UI export flow twice, switches the export repo between
  // branches, and asserts fix.pass && !main.pass.  Restore is unconditional.
  if (prove) {
    const proveResult = await runProve(cfg, spec);
    renderProveResult(proveResult, spec.ticketKey);
    exit(proveResult.discriminates ? 0 : 1);
  }

  // Build the .ptrac fixture from the spec's reproContent.
  // Writes to runner/.runs/{ticketKey}-{runId}/report.ptrac.
  const { path: ptracPath } = buildPtrac(spec.reproContent, spec.ticketKey, runId);

  // Locate the committed upload template fixture.
  // runner/fixtures/deep-toc-export-template.j2 — uploaded via the UI export flow.
  const templatePath = join(here, "..", "fixtures", "deep-toc-export-template.j2");

  // Full UI browser flow: create client, import .ptrac, set PDF template,
  // export with uploaded template, download the PDF.
  const { pdfPath } = await runBrowserExport(
    cfg,
    spec.ticketKey,
    runId,
    ptracPath,
    templatePath,
  );

  // Extract ToC from the downloaded PDF (probe template, all levels visible).
  const rows = await parseTocFromPdf(pdfPath);

  // Verify heading levels against expected assertions.
  const verify = verifyToc(spec, rows);

  // Write run artifacts and print summary.
  writeRun(runDir, { ticketKey: spec.ticketKey, verify });
  const summary = renderSummaryMarkdown({ ticketKey: spec.ticketKey, verify });
  console.log("\n" + summary);

  // Report all parsed rows for transparency.
  console.log("Parsed ToC rows (from PDF x-coordinates):");
  for (const row of rows) {
    console.log(`  level ${row.level}: "${row.label}"`);
  }

  exit(verify.pass ? 0 : 1);
}

main().catch((err: unknown) => {
  console.error("Fatal:", err instanceof Error ? err.message : String(err));
  exit(1);
});
