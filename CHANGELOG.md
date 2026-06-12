# Changelog

## Unreleased

### Changed — PR review (wrap auth + multipart x402 + list filters)
- **sdk-typescript**: `requestMultipart()` now retries on 402 with x402 signing (same as `request()`); `wrapContent()` allows testnet without credentials (matches `certifyContent`)
- **sdk-python**: `wrap_content()` allows testnet without credentials; `list_certificates()` gains `configuration` / `marking_mode` / `anchor_mode` filters
- **mcp-server**: `wrap_content` description documents testnet cap + production auth; multipart requests support x402 retry
- Removed committed `.DS_Store` (already in `.gitignore`)

### Added — Phase 4 audit (SDK)
- **sdk-typescript** / **sdk-python**: `getAuditCoverage`, `sampleAudit`, `auditExport`, `getInclusionProof`

### Added — AI Act 50 Phase 3 (SDK + MCP)
- **sdk-typescript**: `wrapContent()`, unified `detect()`, `getCompositionRecord()`; Phase 3 types (`marking_mode`, `anchor_mode`, `ingredients`, `VottunDetectResponse`, etc.)
- **sdk-python**: `wrap_content()`, `detect()` (text or image), `get_composition_record()`; explicit `ingredients` / config params on `certify_content`
- **mcp-server**: `wrap_content` tool, `get_composition_record` tool; `certify_content` gains `ingredients` + config fields; `detect_watermark` supports image base64 + Phase 3 response fields

### Added

### Added
- Sprint 3 framework integration examples (LangChain, CrewAI/AutoGen skeleton, LangGraph).
- CI workflow for SDK build/compile checks.
- MCP server dependency fix (`zod`).
- Listing/documentation templates scaffold under `docs/` (Sprint 3 prep).

