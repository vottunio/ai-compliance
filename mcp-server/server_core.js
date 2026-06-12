import * as z from "zod/v4";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const skillMd = readFileSync(join(__dirname, "..", "SKILL.md"), "utf-8");

const apiBaseUrl = process.env.AIACT50_API_BASE_URL || "https://app.aiact50.com/api";
const apiKey = process.env.AIACT50_API_KEY || process.env.SMITHERY_API_KEY || "";
const privateKey = process.env.AIACT50_PRIVATE_KEY || "";

function authHeaders() {
  return apiKey ? { "X-API-Key": apiKey } : {};
}

async function signX402Payment(paymentRequiredBase64) {
  try {
    const { signPayment } = await import("@coinbase/x402");
    const requirements = JSON.parse(atob(paymentRequiredBase64));
    const signed = await signPayment(privateKey, requirements);
    return typeof signed === "string" ? signed : btoa(JSON.stringify(signed));
  } catch (e) {
    if (e?.code === "MODULE_NOT_FOUND" || e?.message?.includes("Cannot find module")) {
      throw new Error("x402 payment requires @coinbase/x402. Install: npm install @coinbase/x402");
    }
    throw new Error(`x402 signing failed: ${e?.message || e}`);
  }
}

const ingredientSchema = z.object({
  role: z.string().optional(),
  cert_id: z.string().optional(),
  content_hash: z.string().optional(),
  model_id: z.string().optional(),
  disclosure: z.enum(["full", "hash_only", "nominal", "mixed"]).optional(),
});

async function apiMultipartRequest({ path, formData }) {
  const url = `${apiBaseUrl}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { ...authHeaders() },
    body: formData,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Vottun API error ${res.status}: ${text || res.statusText}`);
  }
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { raw: text };
  }
}

async function apiRequest({ method, path, jsonBody, query }) {
  const url = new URL(`${apiBaseUrl}${path}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    }
  }

  const res = await fetch(url.toString(), {
    method,
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json"
    },
    body: jsonBody !== undefined ? JSON.stringify(jsonBody) : undefined
  });

  // x402 flow: if 402 and we have a private key, sign payment and retry
  if (res.status === 402 && privateKey && !apiKey) {
    const paymentRequired = res.headers.get("PAYMENT-REQUIRED");
    if (paymentRequired) {
      const paymentHeader = await signX402Payment(paymentRequired);
      const retryRes = await fetch(url.toString(), {
        method,
        headers: { "Content-Type": "application/json", "X-PAYMENT": paymentHeader },
        body: jsonBody !== undefined ? JSON.stringify(jsonBody) : undefined,
      });
      const retryText = await retryRes.text();
      if (!retryRes.ok) {
        throw new Error(`Vottun API error ${retryRes.status} (x402): ${retryText || retryRes.statusText}`);
      }
      try { return retryText ? JSON.parse(retryText) : {}; } catch { return { raw: retryText }; }
    }
  }

  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Vottun API error ${res.status}: ${text || res.statusText}`);
  }

  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { raw: text };
  }
}

export function createMcpServer() {
  const server = new McpServer({
    name: "vottun-ai-compliance",
    version: "0.1.0",
    description: "MCP wrapper for Vottun AI Compliance backend endpoints"
  });

  server.registerResource(
    "skill",
    "skill://aiact50/article50-compliance",
    {
      title: "AI Act 50 — Article 50 Compliance Skill",
      description: "Decision tree and policy for autonomous Article 50 compliance. Read this to know WHEN to call certify_content, verify_certificate, and detect_watermark.",
      mimeType: "text/markdown"
    },
    async (uri) => ({
      contents: [{ uri: uri.href, text: skillMd }]
    })
  );

  server.registerTool(
    "certify_content",
    {
      description: "Certify AI-generated text content on-chain (via /v1/certify). Server computes hashes and applies watermarking.",
      inputSchema: z
        .object({
          content: z.string().describe("Text content to certify"),
          content_type: z
            .enum(["social_post", "article", "image", "video", "audio", "document", "thread", "email"])
            .optional()
            .describe("Content category"),
          ai_system: z.string().describe("AI system/model identifier (maps to ai_system in the backend)"),
          classification: z
            .enum(["fully_ai_generated", "ai_assisted", "manipulated", "deepfake"])
            .optional()
            .describe("EU AI Act classification"),
          deployer_disclosure_applied: z
            .boolean()
            .optional()
            .describe("Article 50(4) disclosure applied"),
          parent_cert_id: z.string().optional(),
          metadata: z.record(z.string(), z.unknown()).optional(),
          ai_provider: z.string().optional(),
          requester_role: z.enum(["human", "autonomous_agent", "system_pipeline"]).optional(),
          generation_timestamp: z.string().optional(),
          organization: z.string().optional(),
          purpose: z
            .enum(["marketing", "informational", "legal", "customer_service", "editorial", "research"])
            .optional(),
          distribution_channel: z
            .enum(["web", "social_media", "email", "chatbot", "print", "broadcast"])
            .optional(),
          risk_level: z.enum(["low", "medium", "high"]).optional(),
          language: z.string().optional(),
          sector: z.enum(["pharma", "banking", "insurance", "media", "legal", "general"]).optional(),
          public_interest: z.boolean().optional(),
          deployer: z
            .string()
            .optional()
            .describe("Entity publishing content publicly (Art. 50(4) liability)"),
          approval_chain: z
            .array(z.string())
            .optional()
            .describe("Optional internal approval chain (e.g. editor/legal/cmo)"),
          watermark: z.boolean().optional().describe("Request server-side watermarking (default: true)"),
          marking_mode: z.enum(["standard", "proprietary", "hybrid", "auto"]).optional(),
          anchor_mode: z.enum(["public", "private"]).optional(),
          configuration: z.enum(["A", "B", "C", "D"]).optional(),
          disclosure_mode: z.enum(["full", "hash_only", "nominal", "mixed"]).optional(),
          ingredients: z
            .array(ingredientSchema)
            .optional()
            .describe("Composite certification ingredient declarations (Phase 3)")
        })
        .passthrough()
    },
    async ({ content, ai_system, watermark, ...rest }) => {
      const result = await apiRequest({
        method: "POST",
        path: "/v1/certify",
        jsonBody: {
          content,
          ai_system,
          watermark,
          ...rest
        }
      });

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "certify_batch",
    {
      description: "Certify multiple items in one on-chain transaction (via /v1/batch).",
      inputSchema: z.object({
        items: z.array(
          z.object({
            content: z.string(),
            ai_system: z.string(),
            content_type: z
              .enum(["social_post", "article", "image", "video", "audio", "document", "thread", "email"])
              .optional(),
            classification: z.enum(["fully_ai_generated", "ai_assisted", "manipulated", "deepfake"]).optional(),
            metadata: z.record(z.string(), z.unknown()).optional(),
            deployer: z.string().optional(),
            approval_chain: z.array(z.string()).optional(),
          }).passthrough()
        ).min(1).max(100),
      }),
    },
    async ({ items }) => {
      const result = await apiRequest({
        method: "POST",
        path: "/v1/batch",
        jsonBody: { items },
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result,
      };
    }
  );

  server.registerTool(
    "verify_certificate",
    {
      description: "Verify a certificate by cert id (vtn_...) or a 64-char content hash (via /v1/verify/{id_or_hash}). Public (no auth).",
      inputSchema: z.object({
        id_or_hash: z.string().describe("Certificate id (vtn_...) or content hash (64-char hex)")
      })
    },
    async ({ id_or_hash }) => {
      const result = await apiRequest({
        method: "GET",
        path: `/v1/verify/${encodeURIComponent(id_or_hash)}`
      });

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "detect_watermark",
    {
      description:
        "Unified detect (Phase 3): text or image via /v1/detect. Returns watermark, C2PA, SynthID, marking_signals.",
      inputSchema: z
        .object({
          content: z.string().optional().describe("Text content to analyze"),
          image_base64: z
            .string()
            .optional()
            .describe("Base64-encoded PNG/JPEG/WebP bytes (use instead of content for media)"),
          mime_type: z
            .enum(["image/png", "image/jpeg", "image/webp"])
            .optional()
            .describe("MIME type when image_base64 is set (default image/png)")
        })
        .refine((v) => Boolean(v.content) !== Boolean(v.image_base64), {
          message: "Provide exactly one of content or image_base64"
        })
    },
    async ({ content, image_base64, mime_type }) => {
      let result;
      if (content) {
        result = await apiRequest({
          method: "POST",
          path: "/v1/detect",
          jsonBody: { content }
        });
      } else {
        const bytes = Buffer.from(image_base64, "base64");
        const form = new FormData();
        const blob = new Blob([bytes], { type: mime_type || "image/png" });
        form.append("file", blob, "detect.png");
        result = await apiMultipartRequest({ path: "/v1/detect", formData: form });
      }

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "wrap_content",
    {
      description:
        "C2PA wrap/sign image without full certify+anchor (POST /v1/wrap). Public (no auth).",
      inputSchema: z.object({
        image_base64: z.string().describe("Base64-encoded PNG/JPEG/WebP image bytes"),
        mime_type: z
          .enum(["image/png", "image/jpeg", "image/webp"])
          .optional()
          .describe("Image MIME type (default image/png)"),
        model_id: z.string().optional(),
        ai_system: z.string().optional(),
        marking_mode: z.enum(["standard", "proprietary", "hybrid", "auto"]).optional(),
        cert_id: z.string().optional().describe("Optional cert id to embed in vottun.audit_ref")
      })
    },
    async ({ image_base64, mime_type, model_id, ai_system, marking_mode, cert_id }) => {
      const bytes = Buffer.from(image_base64, "base64");
      const form = new FormData();
      const blob = new Blob([bytes], { type: mime_type || "image/png" });
      form.append("file", blob, "wrap.png");
      if (model_id) form.append("model_id", model_id);
      if (ai_system) form.append("ai_system", ai_system);
      if (marking_mode) form.append("marking_mode", marking_mode);
      if (cert_id) form.append("cert_id", cert_id);

      const result = await apiMultipartRequest({ path: "/v1/wrap", formData: form });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "get_composition_record",
    {
      description: "Fetch composite ingredient tree for a certified composite (GET /v1/composition/{cert_id}).",
      inputSchema: z.object({
        cert_id: z.string().describe("Composite certificate id (vtn_...)")
      })
    },
    async ({ cert_id }) => {
      const result = await apiRequest({
        method: "GET",
        path: `/v1/composition/${encodeURIComponent(cert_id)}`
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "get_inclusion_proof",
    {
      description: "Export Merkle inclusion proof for a privately anchored certificate (Config B/D). Requires API key.",
      inputSchema: z.object({
        cert_id: z.string().describe("Certificate id (vtn_...)")
      })
    },
    async ({ cert_id }) => {
      if (!apiKey) {
        return {
          content: [{ type: "text", text: "Missing AIACT50_API_KEY. get_inclusion_proof requires X-API-Key." }],
          structuredContent: { error: "missing_api_key" }
        };
      }
      const result = await apiRequest({
        method: "GET",
        path: `/v1/audit/inclusion-proof/${encodeURIComponent(cert_id)}`
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "get_audit_coverage",
    {
      description: "Article 50 coverage matrix: marking / robustness / demonstrability per configuration.",
      inputSchema: z.object({
        days: z.number().optional().describe("Lookback days (default 30)")
      })
    },
    async ({ days }) => {
      if (!apiKey) {
        return {
          content: [{ type: "text", text: "Missing AIACT50_API_KEY. get_audit_coverage requires X-API-Key." }],
          structuredContent: { error: "missing_api_key" }
        };
      }
      const result = await apiRequest({
        method: "GET",
        path: "/v1/audit/coverage",
        query: days !== undefined ? { days } : undefined
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "sample_audit",
    {
      description: "Reproducible random audit sample with proof references (POST /v1/audit/sampling).",
      inputSchema: z.object({
        sample_size: z.number().optional(),
        seed: z.string().optional(),
        configuration: z.enum(["A", "B", "C", "D"]).optional()
      })
    },
    async ({ sample_size, seed, configuration }) => {
      if (!apiKey) {
        return {
          content: [{ type: "text", text: "Missing AIACT50_API_KEY. sample_audit requires X-API-Key." }],
          structuredContent: { error: "missing_api_key" }
        };
      }
      const result = await apiRequest({
        method: "POST",
        path: "/v1/audit/sampling",
        jsonBody: {
          sample_size: sample_size ?? 10,
          seed: seed ?? "audit-sample",
          ...(configuration ? { configuration } : {})
        }
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "audit_export",
    {
      description: "Mode-aware audit export JSON bundle (GET /v1/audit/export?format=json).",
      inputSchema: z.object({
        format: z.enum(["json", "csv", "pdf"]).optional(),
        include_inclusion_proofs: z.boolean().optional()
      })
    },
    async ({ format, include_inclusion_proofs }) => {
      if (!apiKey) {
        return {
          content: [{ type: "text", text: "Missing AIACT50_API_KEY. audit_export requires X-API-Key." }],
          structuredContent: { error: "missing_api_key" }
        };
      }
      const result = await apiRequest({
        method: "GET",
        path: "/v1/audit/export",
        query: {
          format: format ?? "json",
          ...(include_inclusion_proofs ? { include_inclusion_proofs: "true" } : {})
        }
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  server.registerTool(
    "get_certificate",
    {
      description: "Get certificate details by certificate id (via /v1/certs/{cert_id}). Requires AIACT50_API_KEY (API key only).",
      inputSchema: z.object({
        certificate_id: z.string().describe("Certificate id (cert_id) to fetch")
      })
    },
    async ({ certificate_id }) => {
      if (!apiKey) {
        return {
          content: [
            {
              type: "text",
              text: "Missing AIACT50_API_KEY (or SMITHERY_API_KEY). get_certificate requires API key auth (X-API-Key)."
            }
          ],
          structuredContent: { error: "missing_api_key" }
        };
      }

      const result = await apiRequest({
        method: "GET",
        path: `/v1/certs/${encodeURIComponent(certificate_id)}`
      });

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result
      };
    }
  );

  return server;
}
