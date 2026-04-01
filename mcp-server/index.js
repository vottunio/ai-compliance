import * as z from "zod/v4";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const apiBaseUrl = process.env.AIACT50_API_BASE_URL || "https://app.aiact50.com/api";
const apiKey = process.env.AIACT50_API_KEY || "";
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

const server = new McpServer({
  name: "vottun-ai-compliance",
  version: "0.1.0",
  description: "MCP wrapper for Vottun AI Compliance backend endpoints"
});

server.registerTool(
  "certify_content",
  {
    description: "Certify AI-generated text content on-chain (via /v1/certify). Server computes hashes and applies watermarking.",
    inputSchema: z
      .object({
        content: z.string().describe("Text content to certify"),
        ai_system: z.string().describe("AI system/model identifier (maps to ai_system in the backend)"),
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
            text: "Missing AIACT50_API_KEY. get_certificate requires API key auth (X-API-Key)."
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

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("MCP server is running...");

