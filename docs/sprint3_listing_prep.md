# Sprint 3 listing preparation (repo-owned)

This doc contains the repo-owned steps that you can do inside `ai-compliance/` before making external submissions.

## 1) Publish the TypeScript SDK package (required by listings)

Most directory listings (Smithery, mcp.so, Anthropic MCP directory, LangChain Hub, LlamaHub, Composio, AgentHub, There's An AI For That) require a publishable npm package.

From repo root:

```bash
cd sdk-typescript
npm install
npm run build
```

Then (outside CI) run:

```bash
npm publish
```

Notes:
- Ensure the package name matches what the directory expects for integrations (see `sdk-typescript/package.json`).
- Bump version as needed before publishing (package.json version).

## 2) Tool names to advertise

The MCP server exposes these tool names:

- `certify_content`
- `verify_certificate`
- `detect_watermark`
- `get_certificate`

If a directory requires a “tool card” or “capabilities list”, include those names + short descriptions (see `mcp-server/index.js` and `mcp-server/README.md`).

## 3) Add directory-specific manifests (templates)

Some directories accept JSON manifests or tool-card metadata.

This repo includes templates you can adapt:
- `docs/listing_tool_card.template.json`
- `listings/` (starter manifests/tool cards for each directory)
- `listings/anthropic-mcp/pr_template.md` (official MCP directory PR starter text)
- `listings/theresanaiforthat/listing_copy.md` (submission copy starter)

## 4) Documentation needed for links

Listings usually link to your repo README. Ensure the README includes:
- quickstart for Python + TypeScript
- “watermark is server-side only” clarification
- MCP server run instructions

