# Listing payload templates (repo-owned)

Directory listings (Smithery, mcp.so / Anthropic MCP, AgentHub, Composio, LangChain Hub, LlamaHub, There's An AI For That) typically require a combination of:

1. A publishable SDK package (npm publish for TypeScript SDK)
2. A JSON manifest / tool card describing the MCP tools + capabilities
3. Links to this repo README + examples

This folder contains *starter* payload templates you can upload/paste when creating the external listings.

## What’s included here

- `smithery/manifest.json` (template)
- `mcp-so/manifest.json` (template)
- `agenthub/tool_card.json` (template)
- `composio/integration.json` (template)
- `langchain-hub/tool_template.json` (template)
- `llamahub/integration.json` (template)
- `anthropic-mcp/pr_template.md` (PR text starter for official MCP directory)
- `theresanaiforthat/listing_copy.md` (submission text starter)

## How to fill versions (recommended)

Before submitting, update versions by ensuring the npm packages are built/published:

```bash
cd sdk-typescript
npm install
npm run build
npm pack
```

If your listing form asks for npm versions, use the version from `sdk-typescript/package.json`:

```bash
cat sdk-typescript/package.json | rg '"version"' -n
```

## MCP tool names (must match the MCP server)

- `certify_content`
- `verify_certificate`
- `detect_watermark`
- `get_certificate`

