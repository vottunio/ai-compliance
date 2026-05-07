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
          watermark: z.boolean().optional().describe("Request server-side watermarking (default: true)")
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
      description: "Detect watermark in text (via /v1/detect). Public (no auth).",
      inputSchema: z.object({
        content: z.string().describe("Text content to detect watermark in")
      })
    },
    async ({ content }) => {
      const result = await apiRequest({
        method: "POST",
        path: "/v1/detect",
        jsonBody: { content }
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
