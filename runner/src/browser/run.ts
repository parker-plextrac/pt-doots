// Browser export flow — full UI customer path (no API seeding):
//   1. Login
//   2. Create client via the "New Doot" button
//   3. Search for and open the new client
//   4. Import .ptrac via the "Import report" button and file chooser
//   5. Open the imported report
//   6. Enable PDF export: Details tab → set Report template to "default pdf (PDF)"
//   7. Export: Export button → PDF (.pdf) → Upload template (file chooser) → Export
//   8. Wait for async export job to complete; a download link appears in the UI
//   9. Click the download link; save the PDF to the run folder
//
// Selectors are taken from a Playwright codegen recording of the real UI flow
// and verified against the live stack.  Native OS file dialogs are not captured
// by codegen; both filechooser events are wired via page.waitForEvent('filechooser')
// set up immediately before the trigger click.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { HarnessConfig } from "../config.ts";
import { performLogin } from "./steps/login.ts";

export interface BrowserRunResult {
  pdfPath: string;
  screenshots: string[];
  tracePath: string;
}

export async function runBrowserExport(
  cfg: HarnessConfig,
  ticketKey: string,
  runId: string,
  ptracPath: string,
  templatePath: string,
): Promise<BrowserRunResult> {
  const headless = process.env["PT_HEADLESS"] !== "false";

  // runDir: runner/.runs/{ticketKey}-{runId}/  (gitignored)
  const here = dirname(fileURLToPath(import.meta.url));
  const runDir = join(here, "..", "..", ".runs", `${ticketKey}-${runId}`);
  const screenshotsDir = join(runDir, "screenshots");
  mkdirSync(screenshotsDir, { recursive: true });

  const screenshots: string[] = [];
  let screenshotIndex = 0;

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
    // --- Step 1: Login -------------------------------------------------------
    await performLogin(page, cfg);
    await screenshot("login-complete");

    // --- Step 2: Navigate to clients and create a new client -----------------
    await page.getByTestId("sidebar-menuitem-clients").click();
    await page.waitForLoadState("networkidle");

    // Use a "client-" prefix so the client name and the .ptrac report name
    // (which is "{ticketKey}-{runId}") do not collide.  The import modal title
    // reads "Import a PlexTrac Report for {clientName}" which would otherwise
    // match the report name search and cause a strict-mode violation.
    const clientName = `${ticketKey}-client-${runId}`;
    await page.getByRole("button", { name: "plus New Doot" }).click();
    await page.getByRole("textbox", { name: "Doot/Project Name" }).fill(clientName);
    await page.getByRole("button", { name: "Submit" }).click();
    await page.waitForLoadState("networkidle");

    // --- Step 3: Search for and open the new client --------------------------
    await page.getByTestId("keyword-input").fill(clientName);
    await page.waitForLoadState("networkidle");
    // first() guards against the name appearing in a header after opening
    await page.getByText(clientName).first().click();
    await page.waitForLoadState("networkidle");
    await screenshot("client-opened");

    // --- Step 4: Import the .ptrac via the UI file chooser ------------------
    // Clicking "Import report" opens a modal (not a direct file dialog).
    // The modal contains a DropZone with a hidden <input type="file">.
    // Use setInputFiles directly on the hidden input (bypasses the OS dialog).
    await page.getByRole("button", { name: "download Import report" }).click();
    const importInput = page.locator('input[type="file"]');
    await importInput.waitFor({ state: "attached", timeout: 10_000 });
    await importInput.setInputFiles(ptracPath);
    await page.getByRole("button", { name: "Submit" }).click();

    // --- Step 5: Open the imported report ------------------------------------
    // The report name matches the .ptrac's report_info.name field, set by
    // fixtureBuilder to "{ticketKey}-{runId}".
    // Wait for the import modal to close before looking for the report name,
    // since the modal title also contains the client name which would cause a
    // strict-mode violation on the text selector.
    const reportName = `${ticketKey}-${runId}`;
    await page.locator('[role="dialog"]').waitFor({ state: "hidden", timeout: 30_000 });
    await page.getByText(reportName).first().click();
    await page.waitForLoadState("networkidle");
    await screenshot("report-loaded");

    // --- Step 6: Verify PDF template is set -----------------------------------
    // The .ptrac fixture is built with the UUID for "default pdf (PDF)".
    // Navigate to Details to confirm the template shows correctly; no UI
    // combobox interaction is needed since the template is set during import.
    await page.getByRole("tab", { name: "Details" }).click();
    await page.waitForLoadState("networkidle");
    await screenshot("pdf-template-set");

    // --- Step 7: Export with uploaded template --------------------------------
    // Set up the download listener before any click that could ultimately
    // trigger the browser download event (the link click in step 8).
    // Use a 120s timeout: the async export job can take up to 2 min, and the
    // download event does not fire until the link is clicked AFTER the job
    // completes.  The default 30s would expire during the job wait.
    const downloadPromise = page.waitForEvent("download", { timeout: 120_000 });
    // Attach a no-op rejection handler so that if the browser closes before
    // this promise resolves, Node.js does not emit an UnhandledPromiseRejection
    // that masks the real error thrown earlier in the flow.
    downloadPromise.catch(() => undefined);

    await page.getByRole("button", { name: "export Export report down" }).click();
    await screenshot("export-dropdown-opened");

    // Scope click to the ant-dropdown-menu to target the menu item precisely.
    // "PDF (.pdf)" is only enabled after a PDF-compatible report template is
    // saved; using the menu scope avoids matching any background text.
    await page.locator(".ant-dropdown-menu").getByText("PDF (.pdf)").click();
    await screenshot("pdf-modal-opened");

    // The "* PDF export template" combobox may also have an Ant Design
    // selection-item span overlay if any template is pre-selected.
    await page.getByRole("combobox", { name: "* PDF export template" }).click({ force: true });
    await screenshot("pdf-template-combobox-opened");

    // Register the upload response watcher BEFORE selecting the file.
    // setInputFiles triggers the upload immediately; registering waitForResponse
    // after setInputFiles creates a race where the response arrives before the
    // watcher is in place.  Attach a no-op rejection handler (mirrors
    // downloadPromise) so an early throw does not produce an unhandled rejection.
    const templateUploadPromise = page.waitForResponse(
      (resp) => resp.url().includes("/template/import/temp"),
      { timeout: 30_000 },
    );
    templateUploadPromise.catch(() => undefined);

    // "Upload template" is an option in the PDF template combobox dropdown.
    // Clicking it shows a DropZone with a hidden file input — the DropZone does
    // not emit a filechooser event, so setInputFiles on the hidden input is the
    // reliable path.  Keep the filechooser attempt as a belt-and-suspenders
    // fallback.
    const templateChooserPromise = page.waitForEvent("filechooser", { timeout: 5_000 });
    await page.getByText("Upload template").click();
    try {
      const templateChooser = await templateChooserPromise;
      await templateChooser.setFiles(templatePath);
    } catch {
      // Filechooser did not fire — set files directly on the hidden input
      // inside the export dialog (.last() skips the import input from step 4).
      const exportDialog = page.locator('[role="dialog"]').last();
      const templateInput = exportDialog.locator('input[type="file"]');
      await templateInput.waitFor({ state: "attached", timeout: 5_000 });
      await templateInput.setInputFiles(templatePath);
    }
    await screenshot("template-uploaded");

    // Await the upload response.  Watcher was registered before setInputFiles
    // so there is no race condition.
    await templateUploadPromise;
    await screenshot("template-upload-complete");

    await page.getByRole("button", { name: "Export", exact: true }).click();
    await screenshot("export-triggered");

    // --- Step 8: Wait for the async export job and download the PDF ----------
    // After clicking Export the modal closes and PlexTrac navigates to the
    // "Export Details" page (breadcrumb: …/Export History/<filename>).
    // That page shows a table; the "File name" cell contains an <a> whose
    // visible text is the output filename (e.g. "…07-01-2026_…cmr2.pdf").
    // The link only appears once the job transitions to "Completed" status.
    // Wait up to 120s for that <td>-scoped link to become visible.
    const dlLocator = page.locator("td a").filter({ hasText: /.pdf/i });
    try {
      await dlLocator.first().waitFor({ state: "visible", timeout: 120_000 });
    } catch {
      await screenshot("download-link-not-found");
      // Check if the export service itself reported a failure (e.g. WeasyPrint
      // SIGSEGV) rather than still being in progress.
      const exportFailed = await page
        .locator("text=Export Failed")
        .isVisible({ timeout: 1_000 })
        .catch(() => false);
      const detail = exportFailed
        ? " The export service reported a failure — check Export Details on the page."
        : "";
      throw new Error(
        `Could not find the PDF filename link in the Export Details table within 120s.${detail} ` +
          "Check download-link-not-found.png to identify the correct selector.",
      );
    }
    await screenshot("export-job-done");
    await dlLocator.first().click();

    const download = await downloadPromise;
    const pdfPath = join(runDir, "export.pdf");
    await download.saveAs(pdfPath);
    await screenshot("export-complete");

    // --- Step 9: Clean up ----------------------------------------------------
    await context.tracing.stop({ path: tracePath });
    await context.close(); // flushes the recorded video
    await browser.close();

    return { pdfPath, screenshots, tracePath };
  } catch (err) {
    // Always clean up browser resources so the process does not hang.
    try {
      await context.tracing.stop({ path: tracePath });
    } catch {
      // tracing may not have started if failure was very early
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
