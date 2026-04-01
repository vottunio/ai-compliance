# Vottun AI Compliance MCP Server

This MCP server exposes 4 tools that call your Vottun AI Compliance backend:

- `certify_content` -> `POST /api/v1/certify`
- `verify_certificate` -> `GET /api/v1/verify/{id_or_hash}`
- `detect_watermark` -> `POST /api/v1/detect`
- `get_certificate` -> `GET /api/v1/certs/{cert_id}` (requires API key)

## Run (stdio / local clients)

```bash
cd mcp-server
npm install
npm run start
```

## Run (Streamable HTTP / Smithery)

```bash
cd mcp-server
npm install
PORT=3001 npm run start:http
```

MCP endpoint:

- `http://localhost:3001/mcp`
- Supports `GET`, `POST`, `DELETE` for Streamable HTTP transport sessions.

## Environment variables

- `VOTTUN_API_BASE_URL` (optional) default: `https://app.aiact50.com/api`
- `VOTTUN_API_KEY` (optional, but required for `get_certificate`)
- `SMITHERY_API_KEY` (optional alias used by `smithery.yaml`, mapped as API key)

