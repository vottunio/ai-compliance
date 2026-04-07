// `process.env` is used to pick up the API key in Node environments.
// We declare `process` to keep the TS build working without adding `@types/node`.
declare const process: { env: Record<string, string | undefined> } | undefined;

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

  // Allow extra keys if backend adds fields:
  [key: string]: unknown;
};

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

  async verifyCertificate(idOrHash: string): Promise<any> {
    // GET /api/v1/verify/{id_or_hash}
    return this.request(`/v1/verify/${encodeURIComponent(idOrHash)}`, { method: "GET" });
  }

  async detectWatermark(content: string): Promise<any> {
    return this.request("/v1/detect", {
      method: "POST",
      headers: { ...this.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ content })
    });
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
    date_from?: string;
    date_to?: string;
  }): Promise<any> {
    if (!this.apiKey) throw new Error("apiKey is required for listCertificates()");
    const params = new URLSearchParams();
    if (options?.offset !== undefined) params.set("offset", String(options.offset));
    if (options?.limit !== undefined) params.set("limit", String(options.limit));
    if (options?.content_type !== undefined) params.set("content_type", options.content_type);
    if (options?.date_from !== undefined) params.set("date_from", options.date_from);
    if (options?.date_to !== undefined) params.set("date_to", options.date_to);

    const qs = params.toString();
    return this.request(`/v1/certs${qs ? `?${qs}` : ""}`, {
      method: "GET",
      headers: this.headers()
    });
  }
}

