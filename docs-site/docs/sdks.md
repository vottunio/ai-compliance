# SDKs

## Backend API

SDKs and the MCP server call these backend endpoints:

- `POST https://app.aiact50.com/api/v1/certify`
- `POST https://app.aiact50.com/api/v1/batch`
- `GET  https://app.aiact50.com/api/v1/verify/{id_or_hash}`
- `POST https://app.aiact50.com/api/v1/detect`
- `GET  https://app.aiact50.com/api/v1/certs/{cert_id}` (requires `X-API-Key`)
- `GET  https://app.aiact50.com/api/v1/certs` (requires `X-API-Key`)

## Testnet vs Mainnet

- No `X-API-Key` => free testnet mode (Base Sepolia; limited operations per IP).
- With `X-API-Key` => mainnet/paid mode.

## Watermark engine note

The watermark algorithm runs **server-side**. The SDK is an API client.
In `POST /v1/certify`, send `watermark=true` (default) to request server-side watermarking.

