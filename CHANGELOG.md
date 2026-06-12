# Changelog

## Unreleased

### Changed — PR review security (wrap + Phase 4)
- **wrap** (`POST /v1/wrap`): now requires same auth as certify (API key / x402 / dev `x-client-id`); testnet IP cap applies
- **sdk-typescript** / **sdk-python**: `wrapContent` / `wrap_content` require credentials; Phase 4 audit methods (`getAuditCoverage`, `sampleAudit`, `auditExport`, `getInclusionProof`)

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

