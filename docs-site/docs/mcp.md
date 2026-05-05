# MCP Server

The MCP server exposes these tools:

- `certify_content` -> `POST /v1/certify`
- `verify_certificate` -> `GET /v1/verify/{id_or_hash}`
- `detect_watermark` -> `POST /v1/detect`
- `get_certificate` -> `GET /v1/certs/{cert_id}` (requires API key)

## Hosted endpoints

| Channel | URL |
|---|---|
| Smithery listing | https://smithery.ai/servers/vottunio/aiact50 |
| HF Space (upstream) | https://huggingface.co/spaces/sergimima/aiact50-mcp |
| MCP HTTP endpoint | `https://sergimima-aiact50-mcp.hf.space/mcp` |

The HF Space is a Docker Space (`hf-space-mcp/Dockerfile`) that pulls `mcp-server/` from `main` at build. Smithery acts as a gateway in front of the HF endpoint.

To trigger a Space rebuild after a `mcp-server/` change: push an empty commit to the HF Space repo, or use **Settings → Factory rebuild** on Hugging Face.

## Run locally

```bash
cd mcp-server
npm install
AIACT50_API_BASE_URL=http://localhost:8000/api npm run start
```

Optional:

```bash
AIACT50_API_BASE_URL=http://localhost:8000/api AIACT50_API_KEY=YOUR_API_KEY npm run start
```

