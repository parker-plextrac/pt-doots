// Entry point: npx tsx src/cli.ts --spec <path> [--headed] [--prove]
//
// Pipeline (normal mode):
//   loadConfig → loadSpec → authenticate → runPreflight → runBrowserExport
//   → parseTocFromPdf → verifyToc → writeRun → print summary
//   → exit 0 (PASS) / exit 1 (FAIL)
//
// Pipeline (--prove mode):
//   ... same as normal through verifyToc ...
//   → findLatestDebugHtml → runProveMode (fix sim + main sim + git-switch pair)
//   → print prove summary → exit 0 (discriminates) / exit 1 (does not discriminate)
import { argv, exit } from "node:process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { loadConfig } from "./config.ts";
import { loadSpec } from "./spec/testSpec.ts";
import { PlexTracApi } from "./api/client.ts";
import { runPreflight } from "./preflight/preflight.ts";
import { runBrowserExport } from "./browser/run.ts";
import { findLatestDebugHtml } from "./verify/debugHtmlParser.ts";
import { parseTocFromPdf } from "./verify/pdfTocParser.ts";
import { verifyToc } from "./verify/diff.ts";
import { runProveMode } from "./verify/proveMode.ts";
import { writeRun, renderSummaryMarkdown } from "./report/reporter.ts";

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

  // API client
  const api = new PlexTracApi(cfg);
  await api.authenticate();

  // Preflight
  const preflight = await runPreflight(api);
  if (preflight.blockers.length > 0) {
    console.error("\nPreflight blockers:");
    for (const b of preflight.blockers) {
      console.error(`  - ${b}`);
    }
    exit(1);
  }

  // Browser export (seeds client + report + narrative, runs async PDF export)
  const { clientId, reportId, pdfPath } = await runBrowserExport(
    cfg,
    api,
    spec.ticketKey,
    runId,
    spec.reproContent.narrativeHtml,
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

  // --prove mode: additionally compare fix vs main via direct WeasyPrint simulation.
  if (prove) {
    console.log("\n--- Prove mode: comparing fix vs main via simulation ---");

    // The debug HTML is written by the first-pass render during the export job.
    const debugHtmlPath = findLatestDebugHtml(cfg.beUploadsDir, clientId, reportId);
    console.log(`  debug HTML: ${debugHtmlPath}`);

    const proveResult = await runProveMode(
      spec,
      debugHtmlPath,
      cfg.exportRepoPath,
      cfg.exportFixBranch,
      runDir,
    );

    console.log("\nProve: fix branch simulation:");
    for (const r of proveResult.fix.results) {
      const mark = r.pass ? "PASS" : "FAIL";
      console.log(`  [${mark}] "${r.label}" expected=${r.expectedLevel} actual=${r.actualLevel ?? "null"}`);
    }

    console.log("\nProve: main branch simulation:");
    for (const r of proveResult.main.results) {
      const mark = r.pass ? "PASS" : "FAIL";
      console.log(`  [${mark}] "${r.label}" expected=${r.expectedLevel} actual=${r.actualLevel ?? "null"}`);
    }

    if (proveResult.discriminates) {
      console.log("\nProve DISCRIMINATES: fix PASS, main FAIL — harness correctly detects the bug.");
      exit(verify.pass ? 0 : 1);
    } else {
      console.log("\nProve DOES NOT DISCRIMINATE — both branches produce the same result.");
      console.log("  This means the harness is not testing the right thing.");
      exit(1);
    }
  }

  exit(verify.pass ? 0 : 1);
}

main().catch((err: unknown) => {
  console.error("Fatal:", err instanceof Error ? err.message : String(err));
  exit(1);
});
