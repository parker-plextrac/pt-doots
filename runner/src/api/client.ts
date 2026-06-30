// Scoped undici Agent provides per-request TLS configuration so the harness
// can talk to the local self-signed stack without touching process.env globally.
import { Agent, fetch as undiciFetch } from "undici";
import { readFileSync } from "node:fs";
import type { HarnessConfig } from "../config.ts";

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
// Import .ptrac:
//   POST /api/v1/client/{clientId}/report/import
//     multipart field "file" — the .ptrac file bytes
//     NOTE: the API does not accept reportId in URL or form data; the .ptrac
//     carries its own report structure. The reportId parameter is held for
//     API symmetry with future increments.

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export class PlexTracApi {
  private readonly cfg: HarnessConfig;
  private readonly agent: Agent;
  private jwtToken: string | null = null;

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

  async importPtrac(clientId: string, _reportId: string, ptracPath: string): Promise<void> {
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
  }
}
