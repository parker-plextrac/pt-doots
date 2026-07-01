# browser module

Drives Playwright to execute the full customer UI flow for end-to-end PDF export repro tests.

## Key Files
- `run.ts` — `runBrowserExport(cfg, ticketKey, runId, ptracPath, templatePath)` — main entry point; returns paths to PDF, screenshots, trace
- `steps/login.ts` — `performLogin(page, cfg)` — two-step FE login (username field → Login button → password field → Login button)

## Flow (full UI — no API seeding)
1. Login
2. Navigate to Clients sidebar; create a new client via "New Doot" button
3. Search for the client and open it
4. Import the .ptrac via "Import report" button + file input (hidden, set via setInputFiles)
5. Open the imported report
6. Navigate to Details tab to verify the PDF report template is set (set via .ptrac fixture UUID)
7. Export: Export button → PDF (.pdf) → PDF export template combobox → "Upload template" + setInputFiles → Export
8. Wait for the page to navigate to "Export Details" page; click the .pdf filename link in the table; save PDF

## Key discovered behaviors
- The .ptrac fixture sets `template: "e2061c6a-ad78-4a96-ab54-3705cb9a7bf5"` (UUID for "default pdf (PDF)") so PDF export is available without UI interaction on the Details tab.
- After clicking "Upload template", a DropZone appears; the file chooser event does NOT fire. Use `setInputFiles` directly on the hidden `input[type="file"]` inside the export dialog.
- The `waitForResponse` for the template upload MUST be registered BEFORE `setInputFiles`. The upload response arrives immediately and is missed if the watcher is set up after.
- After clicking Export, the modal closes and the page navigates to "Export Details" showing a table with status and a filename `.pdf` link.
- The filename link in the `<td>` triggers the download when clicked (no dialog stays open).

## Filechooser / setInputFiles pattern (template upload)
```typescript
// Register watcher BEFORE file selection — upload fires immediately on setInputFiles
const templateUploadPromise = page.waitForResponse(
  (resp) => resp.url().includes("/template/import/temp"),
  { timeout: 30_000 },
);
templateUploadPromise.catch(() => undefined);

const chooserPromise = page.waitForEvent("filechooser", { timeout: 5_000 });
await page.getByText("Upload template").click();
try {
  const chooser = await chooserPromise;
  await chooser.setFiles(templatePath);
} catch {
  // DropZone does not emit filechooser — use hidden input directly
  const exportDialog = page.locator('[role="dialog"]').last();
  await exportDialog.locator('input[type="file"]').waitFor({ state: "attached", timeout: 5_000 });
  await exportDialog.locator('input[type="file"]').setInputFiles(templatePath);
}
await templateUploadPromise;
```

## Download pattern
`downloadPromise = page.waitForEvent("download", { timeout: 120_000 })` is set up before
clicking Export. After clicking Export the page navigates to the Export Details page.
The filename link in the table (`td a` with `.pdf` text) triggers the browser download.
`download.saveAs(pdfPath)` writes the PDF to the run folder.

## Selectors (recorded from live stack via Playwright codegen)
- Clients sidebar: `getByTestId("sidebar-menuitem-clients")`
- New client button: `getByRole("button", { name: "plus New Doot" })`
- Client name input: `getByRole("textbox", { name: "Doot/Project Name" })`
- Import button: `getByRole("button", { name: "download Import report" })`
- Details tab: `getByRole("tab", { name: "Details" })`
- Export dropdown button: `getByRole("button", { name: "export Export report down" })`
- PDF format option (in dropdown menu): `.ant-dropdown-menu` scoped `getByText("PDF (.pdf)")`
- PDF export template combobox: `getByRole("combobox", { name: "* PDF export template" })`
- Upload template option: `getByText("Upload template")`
- Export submit: `getByRole("button", { name: "Export", exact: true })`
- Download link (on Export Details page): `page.locator("td a").filter({ hasText: /.pdf/i })`

## Environment
- `PT_HEADLESS=false` — run headed (requires a display)
- `PT_APP_URL`, `PT_TEST_USER`, `PT_TEST_PASS` — stack coordinates (see config.ts)

## Dependencies
- Depends on: `playwright` (chromium), `../config.ts` (HarnessConfig), `./steps/login.ts`
- Depended on by: `../cli.ts`
