import type { PlexTracApi } from "../api/client.ts";
import { isRecord } from "../util/guards.ts";

const DEBUG_HTML_KEY = "PDF_EXPORT_DEBUG_HTML_FILE";

export interface PreflightReport {
  debugHtmlOn: boolean;
  asyncExport: boolean;
  ctfMode: boolean;
  rapidTemplating: boolean;
  blockers: string[];
}

// Each flag value is an object whose boolean is `.variation`. Absent flag => false.
function flagOn(flags: Record<string, unknown>, key: string): boolean {
  const f = flags[key];
  return isRecord(f) && f["variation"] === true;
}

export function evaluateFlags(flags: Record<string, unknown>): PreflightReport {
  const report: PreflightReport = {
    debugHtmlOn: flagOn(flags, DEBUG_HTML_KEY),
    asyncExport: flagOn(flags, "ASYNC_EXPORT"),
    ctfMode: flagOn(flags, "CTF_MODE"),
    rapidTemplating: flagOn(flags, "rapidTemplating"),
    blockers: [],
  };
  if (!report.debugHtmlOn) {
    report.blockers.push(
      `${DEBUG_HTML_KEY} is off. The structured gate reads the export debug HTML, so enable this feature flag (or its OVERRIDE_${DEBUG_HTML_KEY}=true backend env) before running.`,
    );
  }
  if (report.ctfMode) {
    report.blockers.push("CTF_MODE is on; it swaps the export menu items. Turn it off before running.");
  }
  // asyncExport is NOT a blocker — it tells the browser step to poll a jobId instead of taking a sync blob.
  return report;
}

export async function runPreflight(api: PlexTracApi): Promise<PreflightReport> {
  const flags = await api.getFeatureFlags();
  return evaluateFlags(flags);
}
