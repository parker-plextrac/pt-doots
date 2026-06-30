// Entry point: npx tsx src/cli.ts --spec <path> [--headed] [--prove]
//
// Pipeline:
//   loadConfig → loadSpec → authenticate → runPreflight → runBrowserExport
//   → findLatestDebugHtml → parseTocRows → verifyToc → renderTocPng
//   → writeRun → print summary → exit 0 (PASS) / exit 1 (FAIL)
import { argv, exit } from "node:process";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { loadConfig } from "./config.ts";
import { loadSpec } from "./spec/testSpec.ts";
import { PlexTracApi } from "./api/client.ts";
import { runPreflight } from "./preflight/preflight.ts";
import { runBrowserExport } from "./browser/run.ts";
import { findLatestDebugHtml, parseTocRows } from "./verify/debugHtmlParser.ts";
import { verifyToc } from "./verify/diff.ts";
import { renderTocPng } from "./verify/pdfImage.ts";
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

  if (prove) {
    console.error("Error: --prove is not yet implemented");
    exit(1);
  }

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

  // Browser export
  const { clientId, reportId, pdfPath } = await runBrowserExport(
    cfg,
    api,
    spec.ticketKey,
    runId,
    spec.reproContent.narrativeHtml,
  );

  // Find and parse debug HTML
  const debugHtmlPath = findLatestDebugHtml(cfg.beUploadsDir, clientId, reportId);
  const debugHtml = readFileSync(debugHtmlPath, "utf8");
  const rows = parseTocRows(debugHtml);

  // Verify heading levels
  const verify = verifyToc(spec, rows);

  // Best-effort visual proof (no-op when poppler is absent)
  const pngPath = renderTocPng(pdfPath, runDir);
  if (pngPath !== null) {
    console.log(`Visual proof: ${pngPath}`);
  }

  // Write run artifacts and print summary
  writeRun(runDir, { ticketKey: spec.ticketKey, verify });
  const summary = renderSummaryMarkdown({ ticketKey: spec.ticketKey, verify });
  console.log("\n" + summary);

  // Report all parsed rows for transparency
  console.log("Parsed heading rows:");
  for (const row of rows) {
    console.log(`  level ${row.level}: "${row.label}"`);
  }

  exit(verify.pass ? 0 : 1);
}

main().catch((err: unknown) => {
  console.error("Fatal:", err instanceof Error ? err.message : String(err));
  exit(1);
});
