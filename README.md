# Vottun AI Compliance (EU AI Act Art. 50)

Open-source toolkit for certifying, watermarking, detecting and verifying AI-generated content.

This repository includes:

- Smart contract ABI under `contracts/` (backend uses this)
- Python SDK under `sdk-python/`
- TypeScript SDK under `sdk-typescript/`
- MCP server tools under `mcp-server/`

## Backend API

The SDKs/MCP server call the backend API endpoints:

- `POST https://app.aiact50.com/api/v1/certify`
- `POST https://app.aiact50.com/api/v1/batch`
- `GET  https://app.aiact50.com/api/v1/verify/{id_or_hash}`
- `POST https://app.aiact50.com/api/v1/detect`
- `GET  https://app.aiact50.com/api/v1/certs/{cert_id}` (requires `X-API-Key`)
- `GET  https://app.aiact50.com/api/v1/certs` (requires `X-API-Key`)

### Testnet vs Mainnet mode

- If you do **not** send `X-API-Key`, requests run in **free testnet mode** (10 ops/IP, Base Sepolia).
- If you do send `X-API-Key`, requests use **mainnet / paid mode**.

## Watermark engine note

The watermark algorithm runs **server-side**. The SDK is an API client (it does not implement the watermark engine locally).
In `POST /v1/certify`, send `watermark=true` (default) to request server-side watermarking.

## Getting started

### Python

```bash
pip install vottun-compliance
```

```python
from vottun_compliance import VottunComplianceClient
print(VottunComplianceClient().certify_content(content="Hello world", ai_system="gpt-4o", watermark=True))
```

### TypeScript

```ts
import { VottunComplianceClient } from "@vottun/ai-compliance";

const client = new VottunComplianceClient(); // free testnet mode

const res = await client.certifyContent({
  content: "Hello world",
  ai_system: "gpt-4o",
  watermark: true // server-side watermarking (default)
});
console.log(res);
```

## Local testing (localhost:8000)

Assuming `vottun-ai-backend` is running at `http://localhost:8000`.

### Python SDK

```bash
cd sdk-python
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

```bash
python3 -c "
from vottun_compliance import VottunComplianceClient
client = VottunComplianceClient(base_url='http://localhost:8000/api')
cert = client.certify_content(content='Hello world', ai_system='gpt-4o', watermark=True)
cid = cert.get('cert_id') or cert.get('certificate_id')
print('cert:', cert)
print('verify:', client.verify_certificate(cid))
"
```

### TypeScript SDK

```bash
cd sdk-typescript
npm install
npm run build
```

```bash
cd sdk-typescript && node --input-type=module -e "
import { VottunComplianceClient } from './dist/index.js';
const client = new VottunComplianceClient({ baseUrl: 'http://localhost:8000/api' });
const cert = await client.certifyContent({ content: 'Hello world', ai_system: 'gpt-4o', watermark: true });
const cid = cert.cert_id ?? cert.certificate_id;
const verify = await client.verifyCertificate(cid);
console.log('cert:', cert);
console.log('verify:', verify);
"
```

## MCP server

The MCP server exposes tools:

- `certify_content`
- `verify_certificate`
- `detect_watermark`
- `get_certificate`

See `mcp-server/README.md`.

### MCP server run (localhost:8000)

```bash
cd mcp-server
npm install
VOTTUN_API_BASE_URL=http://localhost:8000/api npm run start
```

Optional: set `VOTTUN_API_KEY` if you want `get_certificate` to work:

```bash
VOTTUN_API_BASE_URL=http://localhost:8000/api VOTTUN_API_KEY=YOUR_API_KEY npm run start
```

Testing `certify_content` / `verify_certificate` / `detect_watermark` is done via any MCP-capable client (Cursor, Claude Desktop, etc.) calling those tool names.

