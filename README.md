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

### Auth modes

The SDK supports three auth modes (in priority order):

| Mode | Config | How it works |
|---|---|---|
| **SaaS** (API key) | `apiKey` / `AIACT50_API_KEY` | Sends `X-API-Key` header. Mainnet, unlimited per tier. |
| **x402 pay-per-use** | `privateKey` / `AIACT50_PRIVATE_KEY` | Auto-signs USDC payment on Base L2 when server returns 402. No API key or subscription needed. |
| **Testnet** (free) | No config | 10 free ops per IP. Base Sepolia. No registration. |

#### x402 pay-per-use (agent-to-agent payments)

For autonomous agents that need to certify content without a subscription:

```python
# Python — requires: pip install eth-account
client = VottunComplianceClient(private_key="0xYOUR_WALLET_PRIVATE_KEY")
result = client.certify_content(content="Hello", ai_system="my-agent")
# Automatically pays 0.005 USDC per certify on Base Sepolia (testnet)
```

```typescript
// TypeScript — requires: npm install @coinbase/x402
const client = new VottunComplianceClient({ privateKey: "0xYOUR_WALLET_PRIVATE_KEY" });
const result = await client.certifyContent({ content: "Hello", ai_system: "my-agent" });
// Automatically pays 0.005 USDC per certify on Base Sepolia (testnet)
```

The SDK handles the full x402 flow automatically: request → 402 response → sign ERC-3009 payment → retry with payment header → done.

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
AIACT50_API_BASE_URL=http://localhost:8000/api npm run start
```

Optional env vars:

```bash
# SaaS mode (API key):
AIACT50_API_BASE_URL=http://localhost:8000/api AIACT50_API_KEY=YOUR_API_KEY npm run start

# x402 pay-per-use mode (wallet private key, requires: npm install @coinbase/x402):
AIACT50_API_BASE_URL=http://localhost:8000/api AIACT50_PRIVATE_KEY=0xYOUR_KEY npm run start
```

Testing `certify_content` / `verify_certificate` / `detect_watermark` is done via any MCP-capable client (Cursor, Claude Desktop, etc.) calling those tool names.

