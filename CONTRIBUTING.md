# Contributing to Vottun AI Compliance

Thanks for contributing. This repo contains:
- `sdk-python/` - Python SDK
- `sdk-typescript/` - TypeScript SDK
- `mcp-server/` - MCP server exposing tools (certify/verify/detect/get_certificate)
- `examples/` - framework integrations and runnable scripts

## How to contribute

1. Open an issue (or comment on an existing one) describing the change.
2. Create a branch and implement the change.
3. Add/adjust documentation in `README.md` or `docs/` as needed.
4. Ensure CI passes (see the GitHub Actions workflow).

## Local verification (recommended)

```bash
# Python SDK: install & bytecode compile
cd sdk-python
python3 -m pip install -e .
python3 -m compileall src

# TypeScript SDK: install & build
cd ../sdk-typescript
npm install
npm run build

# MCP server: install dependencies
cd ../mcp-server
npm install
```

## Style

- Keep examples dependency-light: guard optional framework imports when appropriate.
- Prefer small, readable functions over large monoliths.
- Avoid committing secrets (API keys, tokens, etc.).

