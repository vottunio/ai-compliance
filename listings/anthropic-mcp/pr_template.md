# Anthropic MCP directory submission template

Use this content when opening a PR to the official MCP servers directory (`modelcontextprotocol/servers`).

## Title suggestion

`Add Vottun AI Compliance MCP server`

## PR body template

```md
## Server name
Vottun AI Compliance MCP

## Description
Open-source MCP server for certifying, watermarking, detecting, and verifying AI-generated content using Vottun backend endpoints aligned with EU AI Act Article 50 workflows.

## Package / Repo
- npm package: `vottun-ai-compliance-mcp`
- repository: `https://github.com/<your-org>/ai-compliance`

## Tools
- `certify_content`
- `verify_certificate`
- `detect_watermark`
- `get_certificate`

## Notes
- Watermarking is performed server-side by the backend.
- Free testnet mode works without API key for basic operations; authenticated endpoints require `X-API-Key`.
```

## Checklist before opening PR

- [ ] npm package is published and installable
- [ ] README has setup + env var docs
- [ ] Tool names match `mcp-server/index.js`
- [ ] Repo URL placeholders replaced with final org/url
