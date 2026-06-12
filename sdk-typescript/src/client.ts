import type {
  AnchorMode,
  CompositionIngredient,
  IngredientDisclosureMode,
  MarkingMode,
  ProductConfiguration,
  VottunCompositionRecord,
  VottunDetectResponse,
  VottunWrapResponse,
} from "./types.js";

// `process.env` is used to pick up the API key in Node environments.
// We declare `process` to keep the TS build working without adding `@types/node`.
declare const process: { env: Record<string, string | undefined> } | undefined;

export type {
  AnchorMode,
  CompositionIngredient,
  IngredientDisclosureMode,
  MarkingMode,
  ProductConfiguration,
  VottunCompositionRecord,
  VottunDetectResponse,
  VottunWrapResponse,
} from "./types.js";

export type VottunCertifyRequest = {
  // Text flow (server computes hashes):
  content?: string;
  content_hash?: string;

  // ai system naming:
  ai_system?: string;
  model_id?: string;

  // Optional provenance fields (forwarded as-is):
  creator_hash?: string;
  parent_certificate_id?: string;
  generation_type?: number;
  prompt_hash?: string;
  deployer_disclosure_applied?: boolean;
  metadata_cid?: string;
  content_type?: string;
  creator_id?: string;
  metadata?: Record<string, unknown>;
  watermark?: boolean;
  parent_cert_id?: string;
  ai_provider?: string;
  requester_role?: "human" | "autonomous_agent" | "system_pipeline";
  generation_timestamp?: string;
  organization?: string;
  purpose?: "marketing" | "informational" | "legal" | "customer_service" | "editorial" | "research";
  distribution_channel?: "web" | "social_media" | "email" | "chatbot" | "print" | "broadcast";
  risk_level?: "low" | "medium" | "high";
  language?: string;
  sector?: "pharma" | "banking" | "insurance" | "media" | "legal" | "general";
  public_interest?: boolean;
  deployer?: string;
  approval_chain?: string[];

  // AI Act 50 v2.1 (Phase 3)
  marking_mode?: MarkingMode;
  anchor_mode?: AnchorMode;
  configuration?: ProductConfiguration;
  disclosure_mode?: IngredientDisclosureMode;
  ingredients?: CompositionIngredient[];

  // Allow extra keys if backend adds fields:
  [key: string]: unknown;
};

export type VottunWrapRequest = {
  /** Image bytes (PNG/JPEG/WebP). */
  file: Blob | ArrayBuffer | Uint8Array;
  mimeType?: string;
  filename?: string;
  model_id?: string;
  ai_system?: string;
  marking_mode?: MarkingMode;
  cert_id?: string;
};

export type VottunDetectInput =
  | { content: string }
  | { file: Blob | ArrayBuffer | Uint8Array; mimeType?: string; filename?: string };

export class VottunComplianceClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly timeoutMs: number;
  private readonly privateKey?: string;

  /**
   * @param options.baseUrl   — API base URL (default: https://app.aiact50.com/api)
   * @param options.apiKey    — API key for SaaS/mainnet mode (X-API-Key header)
   * @param options.privateKey — Wallet private key for x402 pay-per-use mode (USDC on Base)
   * @param options.timeoutMs — Request timeout in ms (default: 30000)
   *
   * Auth modes (in priority order):
   * 1. apiKey set         → SaaS channel (X-API-Key header)
   * 2. privateKey set     → x402 channel (auto-sign USDC payment on 402 response)
   * 3. neither set        → testnet (10 free ops, no auth)
   */
  constructor(options?: { baseUrl?: string; apiKey?: string; privateKey?: string; timeoutMs?: number }) {
    this.baseUrl = options?.baseUrl ?? "https://app.aiact50.com/api";
    this.apiKey = options?.apiKey ?? process?.env?.AIACT50_API_KEY;
    this.privateKey = options?.privateKey ?? process?.env?.AIACT50_PRIVATE_KEY;
    this.timeoutMs = options?.timeoutMs ?? 30_000;
  }

  private headers(extra?: Record<string, string>): Record<string, string> {
    const h: Record<string, string> = { ...(extra ?? {}) };
    if (this.apiKey) h["X-API-Key"] = this.apiKey;
    return h;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        signal: controller.signal
      });

      // x402 flow: if 402 and we have a private key, sign payment and retry
      if (res.status === 402 && this.privateKey && !this.apiKey) {
        const paymentRequired = res.headers.get("PAYMENT-REQUIRED");
        if (paymentRequired) {
          const paymentHeader = await this.signX402Payment(paymentRequired);
          const retryController = new AbortController();
          const retryId = setTimeout(() => retryController.abort(), this.timeoutMs);
          try {
            const retryRes = await fetch(`${this.baseUrl}${path}`, {
              ...init,
              headers: {
                ...(init?.headers as Record<string, string> ?? {}),
                "X-PAYMENT": paymentHeader,
              },
              signal: retryController.signal,
            });
            const retryText = await retryRes.text();
            if (!retryRes.ok) {
              throw new Error(`Vottun API error ${retryRes.status} (x402 retry): ${retryText || retryRes.statusText}`);
            }
            return retryText ? (JSON.parse(retryText) as T) : ({} as T);
          } finally {
            clearTimeout(retryId);
          }
        }
      }

      const text = await res.text();
      if (!res.ok) {
        throw new Error(`Vottun API error ${res.status}: ${text || res.statusText}`);
      }
      return text ? (JSON.parse(text) as T) : ({} as T);
    } finally {
      clearTimeout(id);
    }
  }

  /**
   * Sign an x402 payment using ERC-3009 (transferWithAuthorization).
   * Requires @coinbase/x402 package: npm install @coinbase/x402
   */
  private async signX402Payment(paymentRequiredBase64: string): Promise<string> {
    try {
      // Dynamic import so x402 is optional — only needed if using pay-per-use
      const { signPayment } = await import("@coinbase/x402");
      const requirements = JSON.parse(atob(paymentRequiredBase64));
      const signed = await signPayment(this.privateKey!, requirements);
      return typeof signed === "string" ? signed : btoa(JSON.stringify(signed));
    } catch (e: any) {
      if (e?.code === "MODULE_NOT_FOUND" || e?.message?.includes("Cannot find module")) {
        throw new Error(
          "x402 payment requires @coinbase/x402 package. Install it: npm install @coinbase/x402"
        );
      }
      throw new Error(`x402 payment signing failed: ${e?.message || e}`);
    }
  }

  async certifyContent(req: VottunCertifyRequest): Promise<any> {
    // POST /api/v1/certify
    return this.request("/v1/certify", {
      method: "POST",
      headers: { ...this.headers(), "Content-Type": "application/json" },
      body: JSON.stringify(req)
    });
  }

  async certifyBatch(items: VottunCertifyRequest[]): Promise<any> {
    return this.request("/v1/batch", {
      method: "POST",
      headers: { ...this.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ items })
    });
  }

  async verifyCertificate(idOrHash: string): Promise<import("./types").VottunVerifyResponse> {
    // GET /api/v1/verify/{id_or_hash} — Phase 4 returns anchor_proof union
    return this.request(`/v1/verify/${encodeURIComponent(idOrHash)}`, { method: "GET" });
  }

  /** Merkle inclusion proof export for private anchor (Config B/D). Requires API key. */
  async getInclusionProof(certId: string): Promise<import("./types").VottunInclusionProofResponse> {
    if (!this.apiKey) throw new Error("apiKey is required for getInclusionProof()");
    return this.request(`/v1/audit/inclusion-proof/${encodeURIComponent(certId)}`, {
      method: "GET",
      headers: this.headers(),
    });
  }

  /** Article 50 coverage matrix (marking / robustness / demonstrability). Requires API key. */
  async getAuditCoverage(options?: {
    days?: number;
    date_from?: string;
    date_to?: string;
  }): Promise<import("./types").VottunAuditCoverageResponse> {
    if (!this.apiKey) throw new Error("apiKey is required for getAuditCoverage()");
    const params = new URLSearchParams();
    if (options?.days !== undefined) params.set("days", String(options.days));
    if (options?.date_from) params.set("date_from", options.date_from);
    if (options?.date_to) params.set("date_to", options.date_to);
    const qs = params.toString();
    return this.request(`/v1/audit/coverage${qs ? `?${qs}` : ""}`, {
      method: "GET",
      headers: this.headers(),
    });
  }

  /** Reproducible audit sample with proof references. Requires API key. */
  async sampleAudit(body: import("./types").VottunAuditSamplingRequest = {}): Promise<import("./types").VottunAuditSamplingResponse> {
    if (!this.apiKey) throw new Error("apiKey is required for sampleAudit()");
    return this.request("/v1/audit/sampling", {
      method: "POST",
      headers: { ...this.headers(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  /**
   * Mode-aware audit export (json | csv | pdf). Requires API key.
   * For csv/pdf returns Blob; for json returns parsed object.
   */
  async auditExport(options?: {
    format?: "json" | "csv" | "pdf";
    date_from?: string;
    date_to?: string;
    configuration?: string;
    anchor_mode?: string;
    include_inclusion_proofs?: boolean;
  }): Promise<unknown> {
    if (!this.apiKey) throw new Error("apiKey is required for auditExport()");
    const params = new URLSearchParams();
    const fmt = options?.format ?? "json";
    params.set("format", fmt);
    if (options?.date_from) params.set("date_from", options.date_from);
    if (options?.date_to) params.set("date_to", options.date_to);
    if (options?.configuration) params.set("configuration", options.configuration);
    if (options?.anchor_mode) params.set("anchor_mode", options.anchor_mode);
    if (options?.include_inclusion_proofs) params.set("include_inclusion_proofs", "true");
    const res = await fetch(`${this.baseUrl}/v1/audit/export?${params.toString()}`, {
      method: "GET",
      headers: this.headers(),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Vottun API error ${res.status}: ${text || res.statusText}`);
    }
    if (fmt === "json") return res.json();
    return res.blob();
  }

  /** @deprecated Use `detect()` — kept for backward compatibility. */
  async detectWatermark(content: string): Promise<VottunDetectResponse> {
    return this.detect({ content });
  }

  /**
   * Unified detect (Phase 3): text JSON or multipart image.
   * Returns SynthID signal, C2PA parse, watermark, and marking_signals.
   */
  async detect(input: VottunDetectInput): Promise<VottunDetectResponse> {
    if ("content" in input) {
      return this.request<VottunDetectResponse>("/v1/detect", {
        method: "POST",
        headers: { ...this.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({ content: input.content }),
      });
    }
    return this.requestMultipart<VottunDetectResponse>("/v1/detect", this._fileForm(input));
  }

  /**
   * C2PA wrap/sign media without full certify+anchor (POST /v1/wrap).
   * Requires API key, JWT (via headers), or x402 — same gate as certify.
   */
  async wrapContent(req: VottunWrapRequest): Promise<VottunWrapResponse> {
    if (!this.apiKey && !this.privateKey) {
      throw new Error("apiKey or privateKey is required for wrapContent() (auth required since PR security fix)");
    }
    const form = this._fileForm(req);
    if (req.model_id) form.append("model_id", req.model_id);
    if (req.ai_system) form.append("ai_system", req.ai_system);
    if (req.marking_mode) form.append("marking_mode", req.marking_mode);
    if (req.cert_id) form.append("cert_id", req.cert_id);
    return this.requestMultipart<VottunWrapResponse>("/v1/wrap", form);
  }

  /** Fetch composite ingredient tree for a certified composite (GET /v1/composition/{cert_id}). */
  async getCompositionRecord(certId: string): Promise<VottunCompositionRecord> {
    return this.request<VottunCompositionRecord>(
      `/v1/composition/${encodeURIComponent(certId)}`,
      { method: "GET" },
    );
  }

  private _toBlob(
    data: Blob | ArrayBuffer | Uint8Array,
    mimeType: string,
  ): Blob {
    if (typeof Blob !== "undefined" && data instanceof Blob) return data;
    if (data instanceof ArrayBuffer) {
      return new Blob([data], { type: mimeType });
    }
    if (data instanceof Uint8Array) {
      const copy = new Uint8Array(data.byteLength);
      copy.set(data);
      return new Blob([copy.buffer], { type: mimeType });
    }
    return new Blob([data], { type: mimeType });
  }

  private _fileForm(input: {
    file: Blob | ArrayBuffer | Uint8Array;
    mimeType?: string;
    filename?: string;
  }): FormData {
    const mimeType = input.mimeType ?? "image/png";
    const filename = input.filename ?? "image.png";
    const form = new FormData();
    form.append("file", this._toBlob(input.file, mimeType), filename);
    return form;
  }

  private async requestMultipart<T>(path: string, form: FormData): Promise<T> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: this.headers(),
        body: form,
        signal: controller.signal,
      });
      const text = await res.text();
      if (!res.ok) {
        throw new Error(`Vottun API error ${res.status}: ${text || res.statusText}`);
      }
      return text ? (JSON.parse(text) as T) : ({} as T);
    } finally {
      clearTimeout(id);
    }
  }

  async getCertificate(certificateId: string): Promise<any> {
    if (!this.apiKey) throw new Error("apiKey is required for getCertificate()");
    return this.request(`/v1/certs/${encodeURIComponent(certificateId)}`, {
      method: "GET",
      headers: this.headers()
    });
  }

  async listCertificates(options?: {
    offset?: number;
    limit?: number;
    content_type?: string;
    classification?: string;
    purpose?: string;
    sector?: string;
    distribution_channel?: string;
    language?: string;
    configuration?: string;
    marking_mode?: string;
    anchor_mode?: string;
    date_from?: string;
    date_to?: string;
    format?: "json" | "csv";
  }): Promise<any> {
    if (!this.apiKey) throw new Error("apiKey is required for listCertificates()");
    const params = new URLSearchParams();
    if (options?.offset !== undefined) params.set("offset", String(options.offset));
    if (options?.limit !== undefined) params.set("limit", String(options.limit));
    if (options?.content_type !== undefined) params.set("content_type", options.content_type);
    if (options?.classification !== undefined) params.set("classification", options.classification);
    if (options?.purpose !== undefined) params.set("purpose", options.purpose);
    if (options?.sector !== undefined) params.set("sector", options.sector);
    if (options?.distribution_channel !== undefined) params.set("distribution_channel", options.distribution_channel);
    if (options?.language !== undefined) params.set("language", options.language);
    if (options?.configuration !== undefined) params.set("configuration", options.configuration);
    if (options?.marking_mode !== undefined) params.set("marking_mode", options.marking_mode);
    if (options?.anchor_mode !== undefined) params.set("anchor_mode", options.anchor_mode);
    if (options?.date_from !== undefined) params.set("date_from", options.date_from);
    if (options?.date_to !== undefined) params.set("date_to", options.date_to);
    if (options?.format !== undefined) params.set("format", options.format);

    const qs = params.toString();
    return this.request(`/v1/certs${qs ? `?${qs}` : ""}`, {
      method: "GET",
      headers: this.headers()
    });
  }
}

