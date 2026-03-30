# MCP Server

The MCP server exposes these tools:

- `certify_content` -> `POST /v1/certify`
- `verify_certificate` -> `GET /v1/verify/{id_or_hash}`
- `detect_watermark` -> `POST /v1/detect`
- `get_certificate` -> `GET /v1/certs/{cert_id}` (requires API key)

## Run locally

```bash
cd mcp-server
npm install
VOTTUN_API_BASE_URL=http://localhost:8000/api npm run start
```

Optional:

```bash
VOTTUN_API_BASE_URL=http://localhost:8000/api VOTTUN_API_KEY=YOUR_API_KEY npm run start
```

