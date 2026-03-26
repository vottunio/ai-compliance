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

  constructor(options?: { baseUrl?: string; apiKey?: string; timeoutMs?: number }) {
    this.baseUrl = options?.baseUrl ?? "https://app.aiact50.com/api";
    this.apiKey = options?.apiKey ?? process.env.VOTTUN_API_KEY;
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
      const text = await res.text();
      if (!res.ok) {
        throw new Error(`Vottun API error ${res.status}: ${text || res.statusText}`);
      }
      return text ? (JSON.parse(text) as T) : ({} as T);
    } finally {
      clearTimeout(id);
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

