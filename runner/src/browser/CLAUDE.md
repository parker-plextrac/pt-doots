# browser module

Drives Playwright to log in and capture the PDF export pipeline for end-to-end repro tests.

## Key Files
- `run.ts` — `runBrowserExport(cfg, api, ticketKey, runId, narrativeHtml)` — main entry point; returns paths to PDF, screenshots, trace
- `steps/login.ts` — `performLogin(page, cfg)` — two-step FE login (username → submit → password → submit)

## Patterns
- API-seed (createClient + createReport + setNarrative), browser for session/navigation/screenshots, API for export trigger + download
- PDF export button is disabled in FE for freshly-created reports (no PDF template assigned). Export is triggered via `api.triggerExportPdf` with an explicit templateID.
- Working PDF template on local stack: `1bce2389-aa0b-4702-8c4d-44571351268b`. Override via `PT_PDF_TEMPLATE_ID` env var.
- `PT_HEADLESS=false` for headed mode (requires a display).

## Dependencies
- Depends on: `playwright` (chromium), `../api/client.ts` (PlexTracApi), `../config.ts` (HarnessConfig)
- Depended on by: top-level runner entry point (not yet built)
