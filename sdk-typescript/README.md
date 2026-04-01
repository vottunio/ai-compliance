# Vottun AI Compliance TypeScript SDK

## Install

This is a workspace package. In a real publish workflow, you would install `@vottunio/ai-compliance`.

## Usage (free testnet mode)

```ts
import { VottunComplianceClient } from "@vottunio/ai-compliance";

const client = new VottunComplianceClient();

const res = await client.certifyContent({
  content: "Hello world",
  ai_system: "gpt-4o"
});

console.log(res);
```

## Usage (paid/mainnet mode)

```ts
const client = new VottunComplianceClient({ apiKey: "YOUR_API_KEY" });

const cert = await client.certifyContent({
  content: "Hello world",
  ai_system: "gpt-4o"
});

const detail = await client.getCertificate(cert.certificate_id ?? cert.cert_id);
console.log(detail);
```

## API base URL

Default: `https://app.aiact50.com/api` (endpoints are under `/v1/*`).

## Runtime requirement

Default implementation uses `fetch` (Node 18+).

## Local testing (localhost:8000)

Assuming `vottun-ai-backend` is running at `http://localhost:8000`.

```bash
cd ..
cd sdk-typescript
npm install
npm run build
```

```bash
node --input-type=module -e "
import { VottunComplianceClient } from './dist/index.js';
const client = new VottunComplianceClient({ baseUrl: 'http://localhost:8000/api' });
const cert = await client.certifyContent({ content: 'Hello world', ai_system: 'gpt-4o', watermark: true });
const cid = cert.cert_id ?? cert.certificate_id;
const verify = await client.verifyCertificate(cid);
console.log('cert:', cert);
console.log('verify:', verify);
"
```

