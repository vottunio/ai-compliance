# Smithery submission checklist (go-live)

Use this checklist to move from "repo prepared" to "listed on Smithery.ai".

## 1) Required artifacts (already in repo)

- Manifest: `listings/smithery/manifest.json`
- MCP server package metadata: `mcp-server/package.json`
- Smithery deployment config: `smithery.yaml`
- SDK package metadata: `sdk-typescript/package.json`
- Public docs: `README.md`

## 2) Publish npm packages

Smithery listing should reference installable packages.

### TypeScript SDK

```bash
cd sdk-typescript
npm install
npm run build
npm publish --access public
```

### MCP server package

```bash
cd mcp-server
npm install
npm publish --access public
```

## 3) Validate package visibility

```bash
npm view @vottunio/ai-compliance version
npm view vottun-ai-compliance-mcp version
```

Both commands must return versions (not 404).

## 4) Final manifest sanity check

Confirm these values in `listings/smithery/manifest.json`:

- npm SDK package: `@vottunio/ai-compliance`
- MCP package: `vottun-ai-compliance-mcp`
- tool names:
  - `certify_content`
  - `verify_certificate`
  - `detect_watermark`
  - `get_certificate`
- repo URL: `https://github.com/vottunio/ai-compliance`

## 5) Submit to Smithery

- Open [https://smithery.ai](https://smithery.ai)
- Create/update server listing
- Paste/upload manifest content from `listings/smithery/manifest.json`
- Add any requested maintainer contact/details
- Submit for review

## 6) Post-submit verification

- Listing appears publicly in search on Smithery
- Tools displayed match the 4 MCP tools above
- Installation instructions resolve to published npm packages

If any check fails, fix package/manifest and resubmit.
