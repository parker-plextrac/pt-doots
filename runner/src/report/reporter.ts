import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { VerifyResult } from "../verify/diff.ts";

export interface SummaryInput {
  ticketKey: string;
  verify: VerifyResult;
}

export function renderSummaryMarkdown(input: SummaryInput): string {
  const status = input.verify.pass ? "PASS" : "FAIL";
  const head = `# ${input.ticketKey} export verification: ${status}\n\n`;
  const tableHead = "| Heading | Expected | Actual | Result |\n|---|---|---|---|\n";
  const rows = input.verify.results
    .map(
      (r) =>
        `| ${r.label} | ${r.expectedLevel} | ${r.actualLevel ?? "missing"} | ${r.pass ? "ok" : "MISMATCH"} |`,
    )
    .join("\n");
  return head + tableHead + rows + "\n";
}

export function writeRun(
  runDir: string,
  input: SummaryInput,
): { summaryPath: string; resultJsonPath: string } {
  mkdirSync(runDir, { recursive: true });
  const summaryPath = join(runDir, "summary.md");
  const resultJsonPath = join(runDir, "result.json");
  writeFileSync(summaryPath, renderSummaryMarkdown(input));
  writeFileSync(resultJsonPath, JSON.stringify(input.verify, null, 2));
  return { summaryPath, resultJsonPath };
}
