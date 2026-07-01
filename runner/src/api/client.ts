// Scoped undici Agent provides per-request TLS configuration so the harness
// can talk to the local self-signed stack without touching process.env globally.
import { Agent, fetch as undiciFetch } from "undici";
import { readFileSync } from "node:fs";
import type { HarnessConfig } from "../config.ts";
import { isRecord } from "../util/guards.ts";

// Confirmed API contracts (empirically verified against local stack):
//
// Auth:
//   POST /api/v1/authenticate
//     body:    { username: string, password: string }
//     success: { status: "success", token: string, cookie: string, tenant_id: number }
//   Authorization header format: "Bearer <token>"
//
// Feature flags:
//   GET /api/v2/featureFlags (requires auth)
//   response: { status: "success", data: { systemLevel: string, featureFlags: Record<string, unknown> } }
//
// Create client:
//   POST /api/v1/client/create
//     body:    { name: string }
//     success: { status: "success", client_id: number, ... }
//
// Create report:
//   POST /api/v1/client/{clientId}/report/create
//     body:    { name: string }
//     success: { message: "success", report_id: number, doc_id: string, cuid: string }
//
// Set narrative (exec summary sections):
//   PUT /api/v2/tenant/{tenantId}/clients/{clientId}/reports/{reportId}/narrative
//     body:    [{id: string, label: string, text: string}]
//     success: { status: "success" }
//
// Import .ptrac:
//   POST /api/v1/client/{clientId}/report/import
//     multipart field "file" — the .ptrac file bytes
//     response: { status: "success" } — NO report id in response (confirmed)
//     The created report id is recovered via a pre/post GET /reports diff.
//   List reports:
//   GET /api/v1/client/{clientId}/reports → array of { id: number, data: [...] }
//
// Async PDF export:
//   POST /api/experimental/client/{clientId}/report/{reportId}/export/pdf
//     body:    { includeEvidence: boolean, templateID: string, timeZone: string }
//     success: { status: "created", message: string, jobId: string }
//   Poll job:
//   GET /api/experimental/client/{clientId}/report/{reportId}/exports/{jobId}
//     response: { jobId, status: "pending"|"running"|"completed"|"failed", outputFilename, outputMetadata }
//   Download:
//   GET /api/experimental/client/{clientId}/report/{reportId}/exports/{jobId}/download
//     response: PDF bytes (Content-Type: application/pdf)

export class PlexTracApi {
  private readonly cfg: HarnessConfig;
  private readonly agent: Agent;
  private jwtToken: string | null = null;
  private _tenantId: number | null = null;

  get tenantId(): number {
    if (this._tenantId === null) {
      throw new Error("Not authenticated: call authenticate() first");
    }
    return this._tenantId;
  }

  constructor(cfg: HarnessConfig) {
    this.cfg = cfg;
    this.agent = new Agent({ connect: { rejectUnauthorized: false } });
  }

  async authenticate(): Promise<void> {
    const url = `${this.cfg.appUrl}/api/v1/authenticate`;
    const response = await undiciFetch(url, {
      method: "POST",
      dispatcher: this.agent,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: this.cfg.username, password: this.cfg.password }),
    });
    if (!response.ok) {
      throw new Error(`Authentication failed: HTTP ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    if (!isRecord(data) || typeof data["token"] !== "string") {
      throw new Error("Authentication response missing token field");
    }
    this.jwtToken = data["token"];
    if (typeof data["tenant_id"] === "number") {
      this._tenantId = data["tenant_id"];
    }
  }

  private authHeaders(): Record<string, string> {
    if (this.jwtToken === null) {
      throw new Error("Not authenticated: call authenticate() first");
    }
    return { Authorization: `Bearer ${this.jwtToken}` };
  }

  async getFeatureFlags(): Promise<Record<string, unknown>> {
    const url = `${this.cfg.appUrl}/api/v2/featureFlags`;
    const response = await undiciFetch(url, {
      dispatcher: this.agent,
      headers: this.authHeaders(),
    });
    if (!response.ok) {
      throw new Error(`getFeatureFlags failed: HTTP ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    if (
      !isRecord(data) ||
      !isRecord(data["data"]) ||
      !isRecord(data["data"]["featureFlags"])
    ) {
      throw new Error("Unexpected featureFlags response shape");
    }
    return data["data"]["featureFlags"];
  }

  async createClient(name: string): Promise<{ clientId: string }> {
    const url = `${this.cfg.appUrl}/api/v1/client/create`;
    const response = await undiciFetch(url, {
      method: "POST",
      dispatcher: this.agent,
      headers: { ...this.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      throw new Error(`createClient failed: HTTP ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    if (!isRecord(data) || typeof data["client_id"] !== "number") {
      throw new Error("Unexpected createClient response shape");
    }
    return { clientId: String(data["client_id"]) };
  }

  async createReport(clientId: string, name: string): Promise<{ reportId: string }> {
    const url = `${this.cfg.appUrl}/api/v1/client/${clientId}/report/create`;
    const response = await undiciFetch(url, {
      method: "POST",
      dispatcher: this.agent,
      headers: { ...this.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      throw new Error(`createReport failed: HTTP ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    if (!isRecord(data) || typeof data["report_id"] !== "number") {
      throw new Error("Unexpected createReport response shape");
    }
    return { reportId: String(data["report_id"]) };
  }

  // The import endpoint returns {"status":"success"} with no report id (confirmed empirically).
  // We use a pre/post report-list diff to discover the new report id.
  private async listReportIds(clientId: string): Promise<Set<string>> {
    const url = `${this.cfg.appUrl}/api/v1/client/${clientId}/reports`;
    const response = await undiciFetch(url, {
      dispatcher: this.agent,
      headers: this.authHeaders(),
    });
    if (!response.ok) {
      throw new Error(`listReportIds failed: HTTP ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    if (!Array.isArray(data)) {
      throw new Error("Unexpected listReportIds response shape");
    }
    const ids = new Set<string>();
    for (const item of data) {
      if (isRecord(item) && typeof item["id"] === "number") {
        ids.add(String(item["id"]));
      }
    }
    return ids;
  }

  async importPtrac(clientId: string, ptracPath: string): Promise<{ reportId: string }> {
    // Snapshot existing reports so we can identify the newly-created one after import.
    const before = await this.listReportIds(clientId);

    // Build multipart body as a Buffer to avoid the FormData type conflict between
    // @types/node and undici. Buffer is NodeJS.ArrayBufferView, which IS in BodyInit.
    const fileBytes = readFileSync(ptracPath);
    const boundary = `----HarnessFormBoundary${Date.now()}`;
    const prologue = Buffer.from(
      `--${boundary}\r\n` +
        `Content-Disposition: form-data; name="file"; filename="import.ptrac"\r\n` +
        `Content-Type: application/octet-stream\r\n` +
        `\r\n`,
    );
    const epilogue = Buffer.from(`\r\n--${boundary}--\r\n`);
    const body = Buffer.concat([prologue, fileBytes, epilogue]);
    const url = `${this.cfg.appUrl}/api/v1/client/${clientId}/report/import`;
    const response = await undiciFetch(url, {
      method: "POST",
      dispatcher: this.agent,
      headers: {
        ...this.authHeaders(),
        "Content-Type": `multipart/form-data; boundary=${boundary}`,
      },
      body,
    });
    if (!response.ok) {
      const errBody = await response.text();
      throw new Error(`importPtrac failed: HTTP ${response.status} ${errBody}`);
    }

    const after = await this.listReportIds(clientId);
    const newIds = [...after].filter((id) => !before.has(id));
    if (newIds.length !== 1) {
      throw new Error(`Expected 1 new report after import, found ${newIds.length}`);
    }
    const reportId = newIds[0];
    if (reportId === undefined) {
      throw new Error("Internal: newIds[0] unexpectedly undefined");
    }
    return { reportId };
  }

  async setNarrative(
    tenantId: number,
    clientId: string,
    reportId: string,
    sections: ReadonlyArray<{ id: string; label: string; text: string }>,
  ): Promise<void> {
    const url = `${this.cfg.appUrl}/api/v2/tenant/${tenantId}/clients/${clientId}/reports/${reportId}/narrative`;
    const response = await undiciFetch(url, {
      method: "PUT",
      dispatcher: this.agent,
      headers: { ...this.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(sections),
    });
    if (!response.ok) {
      const errBody = await response.text();
      throw new Error(`setNarrative failed: HTTP ${response.status} ${errBody}`);
    }
  }

  // opts.temporaryTemplateName — when provided, the export service resolves the
  // template from uploads/export_templates/temp/<name> instead of using templateId.
  // templateId can be an empty string in that case (the server ignores it).
  async triggerExportPdf(
    clientId: string,
    reportId: string,
    templateId: string,
    opts?: { temporaryTemplateName?: string },
  ): Promise<{ jobId: string }> {
    const base = `${this.cfg.appUrl}/api/experimental/client/${clientId}/report/${reportId}/export/pdf`;
    const exportUrl = new URL(base);
    if (opts?.temporaryTemplateName !== undefined && opts.temporaryTemplateName.length > 0) {
      exportUrl.searchParams.set("temporaryTemplateName", opts.temporaryTemplateName);
    }
    const response = await undiciFetch(exportUrl.toString(), {
      method: "POST",
      dispatcher: this.agent,
      headers: { ...this.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({
        includeEvidence: false,
        templateID: templateId,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }),
    });
    if (!response.ok) {
      const errBody = await response.text();
      throw new Error(`triggerExportPdf failed: HTTP ${response.status} ${errBody}`);
    }
    const data = await response.json();
    if (!isRecord(data) || typeof data["jobId"] !== "string") {
      throw new Error("Unexpected triggerExportPdf response shape");
    }
    return { jobId: data["jobId"] };
  }

  // Polls until the job reaches a terminal state (completed or failed).
  // Throws if the job fails or the timeout is exceeded.
  async pollExportJob(
    clientId: string,
    reportId: string,
    jobId: string,
    maxWaitMs = 120_000,
  ): Promise<void> {
    const url = `${this.cfg.appUrl}/api/experimental/client/${clientId}/report/${reportId}/exports/${jobId}`;
    const deadline = Date.now() + maxWaitMs;
    while (Date.now() < deadline) {
      await new Promise<void>((resolve) => setTimeout(resolve, 2_000));
      const response = await undiciFetch(url, {
        dispatcher: this.agent,
        headers: this.authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`pollExportJob failed: HTTP ${response.status}`);
      }
      const data = await response.json();
      if (!isRecord(data) || typeof data["status"] !== "string") {
        throw new Error("Unexpected pollExportJob response shape");
      }
      const status = data["status"];
      if (status === "completed") {
        return;
      }
      if (status === "failed") {
        const meta = data["outputMetadata"];
        let msg = "unknown error";
        if (Array.isArray(meta)) {
          const first = meta[0];
          if (isRecord(first) && typeof first["message"] === "string") {
            msg = first["message"];
          }
        }
        throw new Error(`Export job failed: ${msg}`);
      }
    }
    throw new Error(`pollExportJob timed out after ${maxWaitMs}ms`);
  }

  async downloadExport(
    clientId: string,
    reportId: string,
    jobId: string,
  ): Promise<Buffer> {
    const url = `${this.cfg.appUrl}/api/experimental/client/${clientId}/report/${reportId}/exports/${jobId}/download`;
    const response = await undiciFetch(url, {
      dispatcher: this.agent,
      headers: this.authHeaders(),
    });
    if (!response.ok) {
      throw new Error(`downloadExport failed: HTTP ${response.status}`);
    }
    return Buffer.from(await response.arrayBuffer());
  }
}
