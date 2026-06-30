import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

// Schema source: product-services-export/tests/mocks/empty_report.ptrac (empirical)
// and agent-skills/plugins/plextrac/reference/ptrac-structure.md (authoritative spec).
//
// Narrative lives at: report_info.exec_summary.custom_fields
// Each entry: { id: string, label: string, text: string } where text is HTML.

export interface ReproContent {
  sectionTitle: string;
  narrativeHtml: string;
}

export interface BuildPtracResult {
  path: string;
}

export function buildPtrac(
  reproContent: ReproContent,
  ticketKey: string,
  runId: string,
): BuildPtracResult {
  const here = dirname(fileURLToPath(import.meta.url));
  // here = <runner>/src/fixture  →  runner root is two levels up
  const runsDir = join(here, "..", "..", ".runs");
  const runDir = join(runsDir, `${ticketKey}-${runId}`);
  mkdirSync(runDir, { recursive: true });
  const path = join(runDir, "report.ptrac");

  const now = Date.now();
  const ptrac = {
    report_info: {
      client_id: 1,
      name: `${ticketKey}-${runId}`,
      description: "",
      status: "Draft",
      created_at: now,
      tags: [],
      reviewers: [],
      template: "default",
      logistics: "",
      reportType: "default",
      includeEvidence: false,
      operators: [],
      report_id: 1,
      source_tenant: { name: "harness", tenant_id: 0 },
      exec_summary: {
        custom_fields: [
          {
            id: "sec-0",
            label: reproContent.sectionTitle,
            text: reproContent.narrativeHtml,
          },
        ],
      },
    },
    client_info: {
      name: "harness",
      client_id: 1,
      doc_type: "client",
      tenant_id: 0,
      fields: [],
    },
    summary: {
      GeneratedOn: new Date(now).toISOString(),
      GeneratedBy: { name: "harness", tenant_id: 0 },
      FlawSummary: {
        critical: { total: 0, open: 0, closed: 0, in_process: 0 },
        high: { total: 0, open: 0, closed: 0, in_process: 0 },
        medium: { total: 0, open: 0, closed: 0, in_process: 0 },
        low: { total: 0, open: 0, closed: 0, in_process: 0 },
        informational: { total: 0, open: 0, closed: 0, in_process: 0 },
        totals: { total_reported: 0, open: 0, closed: 0, in_process: 0 },
      },
      ReportAssets: {},
      ReportMedia: {},
    },
    flaws_array: [],
    procedures: [],
    evidence: [],
  };

  writeFileSync(path, JSON.stringify(ptrac, null, 2));
  return { path };
}
