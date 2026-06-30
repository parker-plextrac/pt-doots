// Browser export flow:
//   1. Seed (API)    — createClient + createReport + setNarrative
//   2. Browser       — login + navigate to report
//   3. Export (API)  — triggerExportPdf + pollExportJob + downloadExport
//   4. Capture       — browser navigates to job page for UX visibility
//
// The PDF export button in the FE is disabled for both createReport and importPtrac
// because neither seeds a PDF-compatible template (reports default to Word type).
// The async export API accepts an explicit templateID and bypasses this restriction.
// See DEFAULT_PDF_TEMPLATE_ID below for the working template on the local stack.
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { HarnessConfig } from "../config.ts";
import type { PlexTracApi } from "../api/client.ts";
import { performLogin } from "./steps/login.ts";

// The only PDF template file present on the local dev stack.
// Override via PT_PDF_TEMPLATE_ID env var for other environments.
const DEFAULT_PDF_TEMPLATE_ID = "1bce2389-aa0b-4702-8c4d-44571351268b";

export interface BrowserRunResult {
  clientId: string;
  reportId: string;
  pdfPath: string;
  screenshots: string[];
  tracePath: string;
}

export async function runBrowserExport(
  cfg: HarnessConfig,
  api: PlexTracApi,
  ticketKey: string,
  runId: string,
): Promise<BrowserRunResult> {
  const templateId = process.env["PT_PDF_TEMPLATE_ID"] ?? DEFAULT_PDF_TEMPLATE_ID;
  const headless = process.env["PT_HEADLESS"] !== "false";

  // runDir lives at runner/.runs/{ticketKey}-{runId}/  (gitignored)
  const here = dirname(fileURLToPath(import.meta.url));
  const runDir = join(here, "..", "..", ".runs", `${ticketKey}-${runId}`);
  const screenshotsDir = join(runDir, "screenshots");
  mkdirSync(screenshotsDir, { recursive: true });

  const screenshots: string[] = [];
  let screenshotIndex = 0;

  // --- Step 1: API seed -------------------------------------------------------

  const { clientId } = await api.createClient(`IO-2294-${runId}`);
  const { reportId } = await api.createReport(clientId, "IO-2294-report");

  const narrativeHtml =
    "<h1>Heading One</h1>" +
    "<h2>Heading Two</h2>" +
    "<h3>Heading Three</h3>" +
    "<h4>Heading Four</h4>" +
    "<h5>Heading Five</h5>" +
    "<h6>Heading Six</h6>";
  await api.setNarrative(api.tenantId, clientId, reportId, [
    { id: "sec-0", label: "Executive Summary", text: narrativeHtml },
  ]);

  // --- Step 2: Browser context ------------------------------------------------

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    recordVideo: { dir: runDir },
  });
  await context.tracing.start({ screenshots: true, snapshots: true });
  const page = await context.newPage();
  const tracePath = join(runDir, "trace.zip");

  async function screenshot(label: string): Promise<void> {
    const num = String(++screenshotIndex).padStart(2, "0");
    const p = join(screenshotsDir, `${num}-${label}.png`);
    await page.screenshot({ path: p });
    screenshots.push(p);
  }

  try {
    // --- Step 3: Login --------------------------------------------------------
    await performLogin(page, cfg);
    await screenshot("login-complete");

    // --- Step 4: Navigate to report -------------------------------------------
    await page.goto(`${cfg.appUrl}/client/${clientId}/report/${reportId}`);
    await page.waitForLoadState("networkidle");
    await screenshot("report-loaded");

    // --- Step 5: Trigger PDF export via API -----------------------------------
    // The FE PDF button is disabled because the report has no PDF-compatible
    // template assigned. The async export API accepts an explicit templateID.
    const { jobId } = await api.triggerExportPdf(clientId, reportId, templateId);

    // Navigate browser to the job detail page so the async UX is captured in
    // the video / trace (matches what a customer would see after clicking export).
    await page.goto(`${cfg.appUrl}/client/${clientId}/report/${reportId}/exports/${jobId}`);
    await page.waitForLoadState("networkidle");
    await screenshot("export-job-page");

    // --- Step 6: Poll and download --------------------------------------------
    await api.pollExportJob(clientId, reportId, jobId);
    const pdfBytes = await api.downloadExport(clientId, reportId, jobId);
    const pdfPath = join(runDir, "export.pdf");
    writeFileSync(pdfPath, pdfBytes);
    await screenshot("export-complete");

    // --- Step 7: Close -------------------------------------------------------
    await context.tracing.stop({ path: tracePath });
    await context.close(); // flushes video.webm
    await browser.close();

    return { clientId, reportId, pdfPath, screenshots, tracePath };
  } catch (err) {
    // Clean up browser resources even on failure so the process doesn't hang.
    try {
      await context.tracing.stop({ path: tracePath });
    } catch {
      // ignore — tracing may not have started if failure was early
    }
    try {
      await context.close();
    } catch {
      // ignore
    }
    try {
      await browser.close();
    } catch {
      // ignore
    }
    throw err;
  }
}
