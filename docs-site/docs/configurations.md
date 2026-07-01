# Product Configurations A / B / C / D

Vottun AI Compliance (EU AI Act Article 50) exposes four named product configurations that determine **how content is marked (L1/L2)** and **where the audit anchor lives (L3/L4)**.

A configuration is a canonical (marking × anchor) pair:

| Configuration | Marking mode  | Anchor mode | eIDAS timestamp | Typical use case                                             |
|:-------------:|:--------------|:------------|:----------------|:-------------------------------------------------------------|
| **A**         | `standard`    | `public`    | no              | Default. Public verifiability on Base L2. Testnet + x402.    |
| **B**         | `standard`    | `private`   | **yes**         | Enterprise Wrap. AESIA / regulated Spanish tenants (default).|
| **C**         | `proprietary` | `public`    | no              | Proprietary marking, still publicly auditable.               |
| **D**         | `proprietary` | `private`   | no              | Fully private stack: proprietary mark + private Merkle log.  |

Backend truth: `config_resolution.CONFIG_MATRIX`.

```python
CONFIG_MATRIX = {
    ProductConfiguration.A: (MarkingMode.STANDARD,    AnchorMode.PUBLIC),
    ProductConfiguration.B: (MarkingMode.STANDARD,    AnchorMode.PRIVATE),
    ProductConfiguration.C: (MarkingMode.PROPRIETARY, AnchorMode.PUBLIC),
    ProductConfiguration.D: (MarkingMode.PROPRIETARY, AnchorMode.PRIVATE),
}
DEFAULT_CONFIGURATION = ProductConfiguration.A
```

Config **B** additionally sets `eidas_enabled = True` (required for AESIA-regulated Spanish enterprises: QTSP timestamp on private Merkle roots).

---

## 1. The two dimensions

### 1.1 Marking mode (L1 watermark + L2 C2PA)

Configurations A/B use `standard` marking; C/D use `proprietary`. You do **not** pick the marking mode directly — you pick the configuration, and the server resolves the mode from `CONFIG_MATRIX`.

| Resolves to    | Used by       | What the server embeds                                                                                              |
|----------------|---------------|---------------------------------------------------------------------------------------------------------------------|
| `standard`     | Config **A/B** | SynthID-style invisible mark (text: ZWJ/ZWNJ; image: PNG tEXt / JPEG comment marker) **+** C2PA v2 manifest sidecar |
| `proprietary`  | Config **C/D** | Vottun lexical / metadata-based mark (custom channel, no SynthID) **+** C2PA v2 manifest sidecar                   |

The **watermark engine runs server-side**. The SDK never signs or embeds locally.

### 1.2 Anchor mode (L3 chain of custody + L4 registry)

| `anchor_mode` | Backend                                                                                                                | Publicly verifiable? |
|---------------|------------------------------------------------------------------------------------------------------------------------|:--------------------:|
| `public`      | Base L2 smart contract (mainnet or Sepolia testnet). Returns `tx_hash` + `block_number`.                               | yes                  |
| `private`     | Append-only Postgres Merkle log with HSM-signed roots; roots may be periodically anchored on-chain. Optional eIDAS QTSP timestamp on each root (Config B). | via inclusion proof |

---

## 2. Where you set the configuration

Three levels of precedence (highest wins):

1. **Per-request** — `configuration` field on `POST /v1/certify` / `POST /v1/batch`
2. **Tenant default** — `PATCH /v1/tenant-config` (persistent across all future certifies)
3. **Platform fallback** — `A` when nothing is set

If you send `marking_mode` or `anchor_mode` explicitly on a request, the backend validates them against the resolved `configuration`. Sending an inconsistent pair returns:

```
400 Configuration B requires marking_mode=standard (got proprietary)
```

The recommended flow is: send only `configuration` (A/B/C/D) and let the server derive `marking_mode` + `anchor_mode`.

---

## 3. Auth channels (independent from A/B/C/D)

Configurations describe **what the platform does with the content**. The auth channel describes **how you talk to the platform**. They are orthogonal — every configuration works on every channel, subject to the endpoint gates in §3.2.

There are three channels. You pick one by setting (or not setting) credentials on the HTTP request:

| Channel        | How you signal it to the server              | Header sent                     | What you get                                                                                                    |
|----------------|----------------------------------------------|---------------------------------|-----------------------------------------------------------------------------------------------------------------|
| **SaaS**       | Send `X-API-Key: <your key>`                 | `X-API-Key: <key>`              | Mainnet. Cert quota and batch flag driven by your plan. **Only channel with access to the audit + admin APIs.** |
| **x402**       | Don't send an API key; wait for `402`, then resend with `X-PAYMENT` | `X-PAYMENT: <base64 payload>` | Agent pay-per-use over USDC on Base L2. Per-call pricing, no subscription.                                     |
| **Testnet**    | Send no auth headers at all                  | *(none)*                        | Free trial: **10 ops per IP**, Base Sepolia. No signup.                                                          |

If both an API key and a wallet are configured on the client, **the API key wins**. x402 only kicks in when the API key is absent and the server returns `402 Payment Required`.

### 3.1 Endpoint access by auth channel

Every endpoint sits in one of three groups. Once you know the group, you know which channels can reach it.

**Group 1 — Public. No auth ever required.**

- `GET  /v1/verify/{id_or_hash}` — verify by cert id or content hash
- `GET  /v1/composition/{cert_id}` — composite ingredient tree
- `POST /v1/detect` — detect watermark / C2PA in text or image
- `GET  /v1/verify/legacy/{content_hash}` — legacy verify

You can hit these from anywhere. Sending an API key is optional (it only adds tenant attribution to failure logs).

**Group 2 — Any channel. Testnet / x402 / SaaS all work.**

- `POST /v1/certify` — certify a single item
- `POST /v1/batch` — certify up to 100 items in one transaction
- `POST /v1/wrap` — C2PA wrap/sign media without full anchor
- `POST /v1/generate` — demo AI-generation endpoint

Rules that apply per channel:

- **Testnet** — hard cap of 10 successful ops per IP.
- **x402** — server returns `402` with a `PAYMENT-REQUIRED` header; the client signs an ERC-3009 USDC transfer authorization and resends with `X-PAYMENT`.
- **SaaS** — the `aicompliance` addon must be active on your tenant, and you have to stay under your monthly quota.

**Group 3 — SaaS only. `X-API-Key` mandatory.**

- `GET  /v1/certs/{cert_id}` — cert detail
- `GET  /v1/certs` — cert listing (filter by `configuration`, `marking_mode`, `anchor_mode`, …)
- `GET  /v1/audit/inclusion-proof/{cert_id}` — Merkle proof (**Config B / D only**)
- `GET  /v1/audit/coverage` — Article 50 coverage matrix
- `POST /v1/audit/sampling` — reproducible auditor sample
- `GET  /v1/audit/export` — JSON / CSV / PDF / AESIA TG13 / TG14 exports
- `GET  /v1/audit/verification-failures` — verify/detect failure log
- `GET  /v1/tenant-config`, `PATCH /v1/tenant-config` — read/write tenant Config A/B/C/D default
- `GET  /v1/tenant-config/audit-log` — config change history
- `GET  /v1/config`, `GET /v1/stats`, `GET /v1/payments` — tenant plan, usage, payment history
- `POST /v1/migrate/mode/preview`, `POST /v1/migrate/mode/execute`, `GET /v1/migrate/mode/{job_id}` — anchor-mode migration

There is no testnet or x402 path into Group 3. If you need any of these you must be on the SaaS channel.

### 3.2 Rule of thumb

- Certifying, wrapping, verifying, detecting → any channel.
- Reading your own certificates, running audits, changing tenant configuration → SaaS only.

---

## 4. Switching between Config A / B / C / D

### 4.1 Per-request override (recommended for agents)

Add `"configuration": "A" | "B" | "C" | "D"` to the certify payload. This request-level value wins over the tenant default.

```http
POST /v1/certify HTTP/1.1
Host: app.aiact50.com
X-API-Key: <YOUR_API_KEY>
Content-Type: application/json

{
  "content": "Board update generated by Claude Sonnet 4.6.",
  "ai_system": "claude-sonnet-4-6",
  "watermark": true,
  "configuration": "B",
  "deployer": "acme-eu",
  "purpose": "informational",
  "distribution_channel": "email",
  "language": "en"
}
```

Same call with cURL:

```bash
curl -X POST https://app.aiact50.com/api/v1/certify \
  -H "X-API-Key: $AIACT50_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Board update generated by Claude Sonnet 4.6.",
    "ai_system": "claude-sonnet-4-6",
    "watermark": true,
    "configuration": "B",
    "deployer": "acme-eu",
    "purpose": "informational",
    "distribution_channel": "email",
    "language": "en"
  }'
```

Language-specific examples (Python, TypeScript, MCP) live in [`sdks.md`](sdks.md) and [`mcp.md`](mcp.md).

#### What changes in the response when you flip `configuration`

Send the exact same payload above but with a different `configuration` value. Everything else stays the same; the fields below flip:

| Field in the certify response | `A`                                | `B`                                | `C`                                     | `D`                                     |
|-------------------------------|------------------------------------|------------------------------------|-----------------------------------------|-----------------------------------------|
| `configuration`               | `"A"`                              | `"B"`                              | `"C"`                                   | `"D"`                                   |
| `marking_mode`                | `"standard"`                       | `"standard"`                       | `"proprietary"`                         | `"proprietary"`                         |
| `anchor_mode`                 | `"public"`                         | `"private"`                        | `"public"`                              | `"private"`                             |
| `pattern`                     | `"standard"`                       | `"standard"`                       | `"proprietary"`                         | `"proprietary"`                         |
| `network`                     | `"eip155:8453"` (Base L2)          | `"vottun-private-log"`             | `"eip155:8453"` (Base L2)               | `"vottun-private-log"`                  |
| `tx_hash`                     | real Base L2 tx (`0x…`)            | synthetic `"merkle:<log>:<index>"` | real Base L2 tx (`0x…`)                 | synthetic `"merkle:<log>:<index>"`      |
| `block_number`                | Base L2 block                      | `0`                                | Base L2 block                           | `0`                                     |
| `anchor_proof.type`           | `"blockchain"`                     | `"merkle_log"`                     | `"blockchain"`                          | `"merkle_log"`                          |
| `anchor_proof.eidas_timestamp`| not present                        | ISO-8601 (mandatory on B)          | not present                             | `null` unless tenant opted in           |
| `watermark_payload`           | 4-byte SynthID payload (`0x…`)     | 4-byte SynthID payload (`0x…`)     | Vottun proprietary payload (`0x…`)      | Vottun proprietary payload (`0x…`)      |
| Downstream detect will show   | `synthid_detected: true`           | `synthid_detected: true`           | `lexical_watermark: true`               | `lexical_watermark: true`               |
| Inclusion-proof endpoint      | not applicable                     | `GET /v1/audit/inclusion-proof/…`  | not applicable                          | `GET /v1/audit/inclusion-proof/…`       |

Full response bodies for each of A / B / C / D are in [§5 Per-configuration reference](#5-per-configuration-reference).

#### Sending a wrong / inconsistent configuration

The server validates three things before it certifies. Each returns `400 Bad Request`.

**1. Unknown configuration letter.** Only `A`, `B`, `C`, `D` are accepted (case-insensitive on multipart, exact on JSON).

```json
POST /v1/certify   { "configuration": "E", ... }

HTTP/1.1 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "enum",
      "loc": ["body", "configuration"],
      "msg": "Input should be 'A', 'B', 'C' or 'D'",
      "input": "E"
    }
  ]
}
```

**2. `configuration` conflicts with an explicit `marking_mode`.** The pair must match `CONFIG_MATRIX` (A/B → standard, C/D → proprietary).

```json
POST /v1/certify
{ "configuration": "C", "marking_mode": "standard", ... }

HTTP/1.1 400 Bad Request
{ "detail": "Configuration C requires marking_mode=proprietary (got standard)" }
```

**3. `configuration` conflicts with an explicit `anchor_mode`.** A/C are `public`, B/D are `private`.

```json
POST /v1/certify
{ "configuration": "C", "anchor_mode": "private", ... }

HTTP/1.1 400 Bad Request
{ "detail": "Configuration C requires anchor_mode=public (got private)" }
```

**Rule to avoid all three:** send only `configuration`. Let the server derive `marking_mode` and `anchor_mode` from the matrix. Send both explicitly only when you're deliberately trying to fail closed (e.g. a compliance test asserting that Config C never anchors privately).

### 4.2 Change the tenant default (persistent)

`PATCH /v1/tenant-config` — requires `X-API-Key`, writes an audit-log row to `provenance_config_audit_log`. After this call, every future certify from this tenant that does **not** send `configuration` will use the new default.

#### Full request body

**Every field is optional.** Send only what you want to change; unspecified fields keep their current value. On top of that, the server *always* derives `default_marking_mode`, `default_anchor_mode` and `eidas_enabled` from `CONFIG_MATRIX` — so those three fields are validated when present but never trusted as the source of truth.

| Field                   | Type                                                | Required | What the server does                                                                                                                                          |
|-------------------------|-----------------------------------------------------|:--------:|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `configuration`         | `"A" \| "B" \| "C" \| "D"`                          | no       | If sent → new default. If omitted → keeps current (default `"A"` for brand-new tenants). Drives derivation of the next three fields.                          |
| `default_marking_mode`  | `"standard" \| "proprietary"`                       | no       | **Validated only.** If sent it must match the matrix pair for the resolved `configuration` (A/B → `standard`, C/D → `proprietary`) or the request is rejected with `400`. The persisted value is always the matrix value. |
| `default_anchor_mode`   | `"public" \| "private"`                             | no       | **Validated only.** If sent it must match the matrix pair (A/C → `public`, B/D → `private`) or the request is rejected with `400`. Persisted value is always the matrix value. |
| `eidas_enabled`         | `boolean`                                           | no       | **Ignored on write.** The persisted value is always `true` for Config B, `false` for A / C / D. Sending `true` on a non-B config does *not* enable eIDAS.       |
| `region`                | `string` (short country / area code, e.g. `"ES"`, `"EU"`) | no  | If sent → replaces current. If omitted → keeps current. `region = "ES"` unlocks AESIA TG13 / TG14 exports and is what `apply_spain_enterprise_defaults` looks for. |

Backend model: `UpdateTenantProductConfigRequest` in `app/agents/aicompliance/api_models.py`.

#### Minimum valid request

Just the field you actually want to change:

```bash
curl -X PATCH https://app.aiact50.com/api/v1/tenant-config \
  -H "X-API-Key: $AIACT50_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "configuration": "D" }'
```

Response — note that `default_marking_mode`, `default_anchor_mode`, and `eidas_enabled` come back from the matrix, not from your input:

```json
{
  "configuration": "D",
  "default_marking_mode": "proprietary",
  "default_anchor_mode": "private",
  "eidas_enabled": false,
  "region": null
}
```

#### Full request (all fields set)

Sending everything is legal, but redundant — the marking/anchor/eIDAS fields must match the matrix or the call fails.

```bash
curl -X PATCH https://app.aiact50.com/api/v1/tenant-config \
  -H "X-API-Key: $AIACT50_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "configuration": "D",
    "default_marking_mode": "proprietary",
    "default_anchor_mode": "private",
    "eidas_enabled": false,
    "region": "EU"
  }'
```

```json
{
  "configuration": "D",
  "default_marking_mode": "proprietary",
  "default_anchor_mode": "private",
  "eidas_enabled": false,
  "region": "EU"
}
```

#### Common variants

**Turn a Spanish tenant into a regulated (Config B + eIDAS) tenant:**

```bash
curl -X PATCH https://app.aiact50.com/api/v1/tenant-config \
  -H "X-API-Key: $AIACT50_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "configuration": "B", "region": "ES" }'
```

Response — `eidas_enabled` flips to `true` automatically because it was Config B:

```json
{
  "configuration": "B",
  "default_marking_mode": "standard",
  "default_anchor_mode": "private",
  "eidas_enabled": true,
  "region": "ES"
}
```

**Update only the region** (leave configuration untouched):

```bash
curl -X PATCH https://app.aiact50.com/api/v1/tenant-config \
  -H "X-API-Key: $AIACT50_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "region": "EU" }'
```

#### Error responses on PATCH

The same matrix-mismatch rules from §4.1 apply. Examples:

```json
PATCH /v1/tenant-config
{ "configuration": "C", "default_marking_mode": "standard" }

HTTP/1.1 400 Bad Request
{ "detail": "Configuration C requires marking_mode=proprietary (got standard)" }
```

```json
PATCH /v1/tenant-config
{ "configuration": "A", "default_anchor_mode": "private" }

HTTP/1.1 400 Bad Request
{ "detail": "Configuration A requires anchor_mode=public (got private)" }
```

#### Read the current default

```bash
curl -H "X-API-Key: $AIACT50_API_KEY" \
  https://app.aiact50.com/api/v1/tenant-config
```

```json
{
  "configuration": "A",
  "default_marking_mode": "standard",
  "default_anchor_mode": "public",
  "eidas_enabled": false,
  "region": null
}
```

#### Inspect the change history

Every successful PATCH writes a row to `provenance_config_audit_log`. Retrieve them:

```bash
curl -H "X-API-Key: $AIACT50_API_KEY" \
  "https://app.aiact50.com/api/v1/tenant-config/audit-log?limit=50"
```

```json
{
  "success": true,
  "items": [
    {
      "id": "01HZ...",
      "client_id": "…",
      "changed_by": "usr_…",
      "previous_config": { "configuration": "A", "eidas_enabled": false, "region": null },
      "new_config":      { "configuration": "D", "eidas_enabled": false, "region": "EU" },
      "created_at": "2026-07-01T10:12:03.417Z"
    }
  ]
}
```

> **Spain / AESIA note.** New tenants with `region = ES` are auto-seeded with Config **B** + `eidas_enabled = true` via `apply_spain_enterprise_defaults` on onboarding.

---

## 5. Per-configuration reference

Each config below lists: what marks are embedded, where the anchor lives, what the certify response looks like, and which follow-up endpoints are meaningful.

### 5.1 Config A — Standard × Public (default)

- **Marking:** SynthID-style invisible watermark + C2PA v2 manifest.
- **Anchor:** Base L2 smart contract (`ContentProvenanceRegistry`). Public tx.
- **eIDAS:** disabled.
- **Auth:** works on testnet, x402, and SaaS.

Request:

```json
POST /v1/certify
{
  "content": "Marketing tweet drafted by GPT-4o.",
  "ai_system": "gpt-4o",
  "watermark": true,
  "configuration": "A",
  "distribution_channel": "social_media"
}
```

Response (fields specific to Config A marked with `←`):

```json
{
  "cert_id": "vtn_01HZ...",
  "certificate_id": "vtn_01HZ...",
  "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "watermarked_content": "Marketing‍tweet drafted...",
  "watermarked_hash": "5f2c...",
  "watermark_payload": "0x9a4b2c1d",
  "c2pa_manifest": { "claim_generator": "vottun-aiact50/1.0", "assertions": [] },
  "c2pa_manifest_cid": "bafybe...",
  "marking_mode": "standard",           // ←
  "marking_mode_applied": "standard",   // ←
  "anchor_mode": "public",              // ←
  "configuration": "A",                 // ←
  "pattern": "standard",
  "tx_hash": "0xabc...",                // ← real Base L2 tx
  "block_number": 12345678,
  "network": "eip155:8453",             // testnet = eip155:84532
  "verify_url": "https://app.aiact50.com/verify/vtn_01HZ...",
  "timestamp": "2026-07-01T10:12:03.417Z",
  "anchor_proof": {
    "type": "blockchain",               // ←
    "tx_hash": "0xabc...",
    "block_number": 12345678,
    "chain_id": "eip155:8453"
  },
  "auth_mode": "saas",                  // "saas" | "x402" | "testnet"
  "created_at": "2026-07-01T10:12:03.417Z"
}
```

Follow-ups that make sense:

- `POST /v1/detect` — should return `synthid_detected: true`, `c2pa_verified: true`, `detected_marking_mode: "standard"`.
- `GET /v1/verify/{cert_id}` — `on_chain_verified: true`, `anchor_proof.type = "blockchain"`.

### 5.2 Config B — Standard × Private (Enterprise Wrap, eIDAS)

- **Marking:** SynthID-style invisible watermark + C2PA v2 manifest.
- **Anchor:** Private append-only Merkle log (Postgres). HSM-signed roots. **eIDAS QTSP timestamp** on every signed root (required, enforced by `eidas_enabled_for_configuration(B) → True`).
- **Auth:** SaaS in practice — inclusion-proof export requires `X-API-Key`.

Request:

```json
POST /v1/certify
{
  "content": "Regulatory disclosure drafted by Aitana.",
  "ai_system": "vottun-aitana-1",
  "watermark": true,
  "configuration": "B",
  "sector": "banking",
  "purpose": "legal",
  "deployer": "acme-bank-es",
  "language": "es"
}
```

Response (Config B specific fields):

```json
{
  "cert_id": "vtn_01HZ...",
  "configuration": "B",
  "marking_mode": "standard",
  "anchor_mode": "private",
  "pattern": "standard",
  "tx_hash": "merkle:log_es_prod:4521",   // synthetic — NOT an on-chain tx
  "block_number": 0,                       // 0 by design for private anchor
  "network": "vottun-private-log",
  "anchor_proof": {
    "type": "merkle_log",
    "log_id": "log_es_prod",
    "leaf_index": 4521,
    "signed_root": "0x9f...",
    "eidas_timestamp": "2026-07-01T10:12:04Z",
    "on_chain_root_tx_hash": "0xdead..."   // optional; set once the root batch is later anchored
  },
  "content_hash": "e3b0c...",
  "watermark_payload": "0x9a4b2c1d",
  "c2pa_manifest_cid": "bafybe...",
  "auth_mode": "saas"
}
```

Follow-up that only works on Config B / D:

```bash
curl -H "X-API-Key: $KEY" \
  https://app.aiact50.com/api/v1/audit/inclusion-proof/vtn_01HZ...
```

```json
{
  "type": "merkle_log",
  "cert_id": "vtn_01HZ...",
  "log_id": "log_es_prod",
  "leaf_index": 4521,
  "leaf_digest": "5f2c...",
  "root_hash": "0x9f...",
  "inclusion_proof": "0xa1a2...b7b8",     // concatenated sibling hashes
  "signed_root": "0x9f...",
  "signed_leaf": "0x88...",
  "eidas_timestamp": "2026-07-01T10:12:04Z",
  "on_chain_root_tx_hash": "0xdead..."
}
```

### 5.3 Config C — Proprietary × Public

- **Marking:** Vottun proprietary lexical / metadata mark + C2PA v2. No SynthID payload.
- **Anchor:** Base L2 (`ContentProvenanceRegistry`). Public tx.
- **eIDAS:** disabled.
- **Auth:** any channel.

Request:

```json
POST /v1/certify
{
  "content": "Blog article on retail trends.",
  "ai_system": "vottun-editorial-1",
  "watermark": true,
  "configuration": "C",
  "content_type": "article",
  "purpose": "editorial"
}
```

Response:

```json
{
  "cert_id": "vtn_01HZ...",
  "configuration": "C",
  "marking_mode": "proprietary",
  "marking_mode_applied": "proprietary",
  "anchor_mode": "public",
  "pattern": "proprietary",
  "watermarked_content": "...",           // proprietary lexical variant
  "watermark_payload": "0xdead1337",
  "c2pa_manifest_cid": "bafybe...",
  "tx_hash": "0xabc...",
  "block_number": 12345680,
  "network": "eip155:8453",
  "anchor_proof": {
    "type": "blockchain",
    "tx_hash": "0xabc...",
    "block_number": 12345680,
    "chain_id": "eip155:8453"
  },
  "auth_mode": "saas"
}
```

Detect on Config C content returns `detected_marking_mode: "proprietary"`, `synthid_detected: false`, `c2pa_verified: true`.

### 5.4 Config D — Proprietary × Private

- **Marking:** Vottun proprietary mark + C2PA v2.
- **Anchor:** Private Merkle log.
- **eIDAS:** disabled by default (opt-in via `PATCH /v1/tenant-config` if needed).
- **Auth:** SaaS in practice — inclusion proofs require `X-API-Key`.

Request:

```json
POST /v1/certify
{
  "content": "Internal customer-service reply draft.",
  "ai_system": "vottun-cs-1",
  "watermark": true,
  "configuration": "D",
  "purpose": "customer_service",
  "distribution_channel": "chatbot"
}
```

Response mirrors Config B's shape (private anchor) but with `marking_mode: "proprietary"` and no `eidas_timestamp` unless explicitly enabled:

```json
{
  "cert_id": "vtn_01HZ...",
  "configuration": "D",
  "marking_mode": "proprietary",
  "anchor_mode": "private",
  "pattern": "proprietary",
  "tx_hash": "merkle:log_default:11987",
  "block_number": 0,
  "network": "vottun-private-log",
  "anchor_proof": {
    "type": "merkle_log",
    "log_id": "log_default",
    "leaf_index": 11987,
    "signed_root": "0xba...",
    "eidas_timestamp": null
  },
  "auth_mode": "saas"
}
```

Inclusion proof export works exactly the same as Config B.

---

## 6. Verify — response differs by configuration

`GET /v1/verify/{id_or_hash}` is public (no auth). What comes back depends on the configuration under which the cert was issued.

Common fields (all configs):

```json
{
  "cert_id": "vtn_01HZ...",
  "status": "valid",                         // valid | not_found | invalid
  "content_hash": "e3b0c...",
  "ai_system": "claude-sonnet-4-6",
  "classification": "fully_ai_generated",
  "provider": "anthropic",
  "created_at": "2026-07-01T10:12:03.417Z",
  "marking_mode": "standard",
  "anchor_mode": "public",
  "configuration": "A",
  "pattern": "standard",
  "verify_url": "https://app.aiact50.com/verify/vtn_01HZ...",
  "verification_result": "valid"
}
```

Adds on **Config A / C (public anchor)**:

```json
{
  "chain": "eip155:8453",
  "tx_hash": "0xabc...",
  "block_number": 12345678,
  "on_chain_verified": true,
  "anchor_proof": {
    "type": "blockchain",
    "tx_hash": "0xabc...",
    "block_number": 12345678,
    "chain_id": "eip155:8453"
  }
}
```

Adds on **Config B / D (private anchor)**:

```json
{
  "chain": "vottun-private-log",
  "tx_hash": "merkle:log_es_prod:4521",
  "block_number": 0,
  "on_chain_verified": false,          // becomes true once the root batch is later anchored on-chain
  "anchor_proof": {
    "type": "merkle_log",
    "log_id": "log_es_prod",
    "leaf_index": 4521,
    "inclusion_proof": null,           // fetched separately via /v1/audit/inclusion-proof/{cert_id}
    "signed_root": "0x9f...",
    "eidas_timestamp": "2026-07-01T10:12:04Z",     // Config B only
    "on_chain_root_tx_hash": "0xdead..."
  }
}
```

---

## 7. Detect — response fields tell you which config produced the content

`POST /v1/detect` is public. The response includes `detected_marking_mode` and a `marking_signals` block that lets you infer the origin config:

```json
{
  "watermark_detected": true,
  "confidence": 0.94,
  "extracted_payload": "0x9a4b2c1d",
  "matched_cert_id": "vtn_01HZ...",
  "hash_match": true,
  "c2pa_verified": true,
  "c2pa_manifest": { "claim_generator": "vottun-aiact50/1.0", "assertions": [] },
  "synthid_detected": true,               // true on Config A/B, false on C/D
  "synthid_confidence": 0.91,
  "detected_marking_mode": "standard",    // standard on A/B, proprietary on C/D
  "marking_signals": {
    "image_watermark": false,
    "lexical_watermark": false,           // true on Config C/D
    "upstream_c2pa": false,
    "synthid": true,                      // true on Config A/B
    "c2pa_present": true
  }
}
```

Mapping:

| Signals seen                                              | Likely origin config           |
|-----------------------------------------------------------|:-------------------------------|
| `synthid: true`, `c2pa_present: true`                     | A or B                         |
| `lexical_watermark: true`, `c2pa_present: true`           | C or D                         |
| `c2pa_present: true` only                                 | any config with `watermark: false` |

Detect **cannot** distinguish public vs private anchor by itself — that is what `verify` / `anchor_proof.type` is for.

---

## 8. Audit endpoints (SaaS only, cross-configuration)

Auditor / compliance-officer view. All require `X-API-Key`.

### 8.1 Coverage matrix

```
GET /v1/audit/coverage?days=30
```

```json
{
  "success": true,
  "days": 30,
  "configurations": [
    { "configuration": "A", "total": 812, "marking": { "count": 812, "pct": 100.0 }, "robustness": { "count": 812, "pct": 100.0 }, "demonstrability": { "count": 812, "pct": 100.0 } },
    { "configuration": "B", "total": 213, "marking": { "count": 213, "pct": 100.0 }, "robustness": { "count": 213, "pct": 100.0 }, "demonstrability": { "count": 210, "pct": 98.6 } },
    { "configuration": "C", "total": 41,  "marking": { "count": 41,  "pct": 100.0 }, "robustness": { "count": 41,  "pct": 100.0 }, "demonstrability": { "count": 41,  "pct": 100.0 } },
    { "configuration": "D", "total": 17,  "marking": { "count": 17,  "pct": 100.0 }, "robustness": { "count": 17,  "pct": 100.0 }, "demonstrability": { "count": 15,  "pct": 88.2 } }
  ],
  "totals": { "certificates": 1083, "with_watermark": 1083, "with_c2pa": 1083 }
}
```

### 8.2 Reproducible auditor sampling

```
POST /v1/audit/sampling
{ "sample_size": 25, "seed": "aesia-q3-2026", "configuration": "B" }
```

Same seed + same population → same sample. Items include `proof_reference` so you can jump directly to `/v1/verify` or `/v1/audit/inclusion-proof`.

### 8.3 Mode-aware export

```
GET /v1/audit/export?format=json&configuration=B&include_inclusion_proofs=true
GET /v1/audit/export?format=csv
GET /v1/audit/export?format=pdf
GET /v1/audit/export?aesia_template=tg13     # AESIA TG13 JSON
GET /v1/audit/export?aesia_template=tg14     # AESIA TG14 JSON
```

`aesia_template=auto` picks TG13/TG14 based on tenant region.

### 8.4 Inclusion proof (Config B / D only)

Documented in §5.2. Not applicable to Config A / C — the tx hash on Base L2 **is** the proof.

---

## 9. Errors you may see when switching configurations

| Status | Message                                                                       | Cause                                                                                 |
|:------:|-------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| `400`  | `Configuration B requires marking_mode=standard (got proprietary)`            | Inconsistent `marking_mode` / `configuration` pair.                                   |
| `400`  | `Configuration A requires anchor_mode=public (got private)`                   | Same, for `anchor_mode`.                                                              |
| `400`  | `Invalid marking_mode: 'foo'. Allowed: standard, proprietary`                 | Enum typo (only `standard` and `proprietary` are customer-selectable).                |
| `402`  | `Payment required` + `PAYMENT-REQUIRED` header                                | x402 flow. SDK auto-signs when `AIACT50_PRIVATE_KEY` is set.                          |
| `403`  | `AI Compliance addon must be activated to certify content`                    | SaaS channel only. Testnet / x402 bypass this.                                        |
| `403`  | `Client not found or inactive.`                                               | API key whose client no longer exists in this environment.                            |
| `403`  | `Batch certification is not enabled for your plan.`                           | SaaS-only limit, independent of the configuration.                                    |
| `429`  | `Monthly certification limit reached (X/Y).`                                  | SaaS plan quota. Testnet has its own 10-ops-per-IP cap.                               |
| `503`  | `Blockchain service is not configured.`                                       | Config A / C need `CONTENT_REGISTRY_ADDRESS` env on the backend.                      |

---

## 10. Quick decision matrix — which config should I pick?

| Situation                                                                                       | Pick   |
|-------------------------------------------------------------------------------------------------|:------:|
| Cheapest, publicly verifiable default with SynthID.                                             | **A**  |
| AESIA-regulated Spanish enterprise (or need QTSP timestamps).                                   | **B**  |
| Proprietary marking (SynthID unavailable / custom mark wanted) but public anchor.               | **C**  |
| Regulator forbids public on-chain data disclosure but still needs proprietary mark.             | **D**  |
| Just testing.                                                                                   | **A** on testnet mode (no keys) |
| Autonomous agent, no signup, wants to pay per cert.                                             | **A** on x402 mode              |

---

## 11. Environment variable reference

| Variable                | Where     | Purpose                                                                                                            |
|-------------------------|-----------|--------------------------------------------------------------------------------------------------------------------|
| `AIACT50_API_BASE_URL`  | SDK / MCP | Backend base URL. Default `https://app.aiact50.com/api`. Use `http://localhost:8000/api` for local dev.            |
| `AIACT50_API_KEY`       | SDK / MCP | SaaS mode. Sent as `X-API-Key`.                                                                                    |
| `SMITHERY_API_KEY`      | MCP only  | Alias for `AIACT50_API_KEY`, honoured on Smithery listings.                                                        |
| `AIACT50_PRIVATE_KEY`   | SDK / MCP | x402 mode. `0x…` wallet private key. Requires `@coinbase/x402` (TS) or `eth-account` (Py).                         |

`smithery.yaml`:

```yaml
runtime: "typescript"
startCommand:
  type: "http"
  command: "npm --prefix mcp-server run start:http"
  configSchema:
    type: "object"
    properties:
      apiKey:      { type: "string", description: "Vottun API key (optional — omit for free testnet mode)" }
      privateKey:  { type: "string", description: "Wallet private key for x402 pay-per-use (USDC on Base)." }
    required: []
  env:
    AIACT50_API_BASE_URL: "https://app.aiact50.com/api"
    AIACT50_API_KEY:      "{{config.apiKey}}"
    AIACT50_PRIVATE_KEY:  "{{config.privateKey}}"
```

---

## 12. Related backend files (source of truth)

Public repos only expose the SDK/MCP surface — ground truth for the config matrix lives in the backend:

- `app/agents/aicompliance/config_resolution.py` — `CONFIG_MATRIX`, `resolve_certification_config`, `eidas_enabled_for_configuration`
- `app/agents/aicompliance/models.py` — `ProductConfiguration`, `MarkingMode`, `AnchorMode`, `CertifyRequest`, `CertifyResponse`, `VerifyResponseV2`, `AnchorProof`
- `app/agents/aicompliance/api.py` — `/v1/certify`, `/v1/verify/*`, `/v1/detect`, `/v1/wrap`, `/v1/audit/*`, `/v1/tenant-config`
- `app/agents/aicompliance/api_models.py` — `TenantProductConfigResponse`, `AuditCoverageResponse`, `AuditSamplingRequest/Response`, `InclusionProofResponse`
- `app/agents/aicompliance/blockchain_anchor.py` — Config A / C public path (Base L2)
- `app/agents/aicompliance/private_log_anchor.py` — Config B / D private path (Postgres Merkle log + eIDAS)
- `app/agents/aicompliance/spain_defaults.py` — auto-seed Config B for `region = ES`
