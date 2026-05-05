---
title: Vottun AI Compliance MCP
emoji: 🔒
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Vottun AI Compliance — MCP Server

Streamable-HTTP MCP server for the EU AI Act Art. 50 compliance toolkit (certify / verify / detect / get_certificate).

- MCP endpoint: `https://<your-space>.hf.space/mcp`
- Source: https://github.com/vottunio/ai-compliance

## Configuration (Space secrets)

Set these in **Settings → Repository secrets**:

| Secret | Required | Notes |
|---|---|---|
| `AIACT50_API_BASE_URL` | optional | Defaults to `https://app.aiact50.com/api` |
| `AIACT50_API_KEY` | optional | SaaS mode (mainnet, unlimited per tier) |
| `AIACT50_PRIVATE_KEY` | optional | x402 pay-per-use (USDC on Base L2) |

If neither key is set, the server runs in free testnet mode.
