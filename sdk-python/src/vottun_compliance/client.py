from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx


DEFAULT_BASE_URL = "https://app.aiact50.com/api"
# DEFAULT_BASE_URL = "http://your_local_ip:port/api"


def _strip_none(d: dict[str, Any]) -> dict[str, Any]:
    """Remove keys with value None (keeps server request payload clean)."""
    return {k: v for k, v in d.items() if v is not None}


@dataclass
class VottunComplianceClient:
    """
    Client for the Vottun AI Compliance backend.

    Auth modes (in priority order):
    1. api_key set        → SaaS channel (X-API-Key header)
    2. private_key set    → x402 channel (auto-sign USDC payment on 402 response)
    3. neither set        → testnet (10 free ops, no auth)

    x402 pay-per-use requires: pip install eth-account
    """

    base_url: str = DEFAULT_BASE_URL
    api_key: Optional[str] = None
    private_key: Optional[str] = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self._client = httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def _headers(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if extra:
            headers.update(extra)
        return headers

    def _request_with_x402(
        self, method: str, url: str, headers: dict[str, str], **kwargs: Any
    ) -> httpx.Response:
        """Make a request; if 402 and private_key is set, sign payment and retry."""
        res = self._client.request(method, url, headers=headers, **kwargs)
        if res.status_code == 402 and self.private_key and not self.api_key:
            payment_required = res.headers.get("PAYMENT-REQUIRED")
            if payment_required:
                payment_header = self._sign_x402_payment(payment_required)
                retry_headers = {**headers, "X-PAYMENT": payment_header}
                res = self._client.request(method, url, headers=retry_headers, **kwargs)
        return res

    def _sign_x402_payment(self, payment_required_b64: str) -> str:
        """Sign an x402 payment using ERC-3009 (transferWithAuthorization).

        Requires eth-account: pip install eth-account
        """
        import base64
        import json

        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data
        except ImportError:
            raise ImportError(
                "x402 payment requires eth-account package. Install it: pip install eth-account"
            )

        requirements = json.loads(base64.b64decode(payment_required_b64).decode("utf-8"))

        # Extract payment details from the 402 response
        accept = requirements.get("accepts", [{}])[0] if requirements.get("accepts") else requirements
        pay_to = accept.get("payTo") or accept.get("to", "")
        amount = accept.get("maxAmountRequired") or accept.get("amount", "0")
        nonce = accept.get("nonce", "0x" + "0" * 64)
        valid_after = accept.get("validAfter", "0")
        valid_before = accept.get("validBefore", str(2**256 - 1))
        asset = accept.get("asset", "")
        chain_id = accept.get("chainId") or requirements.get("chainId", 84532)
        domain_name = accept.get("name", "USDC")
        domain_version = accept.get("version", "2")

        # Build EIP-712 typed data for transferWithAuthorization (ERC-3009)
        acct = Account.from_key(self.private_key)
        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "TransferWithAuthorization": [
                    {"name": "from", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "validAfter", "type": "uint256"},
                    {"name": "validBefore", "type": "uint256"},
                    {"name": "nonce", "type": "bytes32"},
                ],
            },
            "primaryType": "TransferWithAuthorization",
            "domain": {
                "name": domain_name,
                "version": domain_version,
                "chainId": int(chain_id),
                "verifyingContract": asset,
            },
            "message": {
                "from": acct.address,
                "to": pay_to,
                "value": int(amount),
                "validAfter": int(valid_after),
                "validBefore": int(valid_before),
                "nonce": bytes.fromhex(nonce.removeprefix("0x")) if isinstance(nonce, str) else nonce,
            },
        }

        signable = encode_typed_data(full_message=typed_data)
        signed = acct.sign_message(signable)

        payment_payload = {
            "x402Version": 2,
            "scheme": "exact",
            "network": requirements.get("network", f"eip155:{chain_id}"),
            "payload": {
                "signature": signed.signature.hex(),
                "authorization": {
                    "from": acct.address,
                    "to": pay_to,
                    "value": str(amount),
                    "validAfter": str(valid_after),
                    "validBefore": str(valid_before),
                    "nonce": nonce,
                },
            },
        }
        return base64.b64encode(json.dumps(payment_payload).encode()).decode()

    def certify_content(
        self,
        *,
        content: Optional[str] = None,
        content_hash: Optional[str] = None,
        ai_system: Optional[str] = None,
        model_id: Optional[str] = None,
        watermark: bool = True,
        deployer: Optional[str] = None,
        approval_chain: Optional[list[str]] = None,
        marking_mode: Optional[str] = None,
        anchor_mode: Optional[str] = None,
        configuration: Optional[str] = None,
        disclosure_mode: Optional[str] = None,
        ingredients: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Certify text content (server computes hashes and applies watermark server-side).

        You must provide:
        - either `content` or `content_hash`
        - either `ai_system` or `model_id`
        """
        payload = _strip_none(
            {
                "content": content,
                "content_hash": content_hash,
                "ai_system": ai_system,
                "model_id": model_id,
                "watermark": watermark,
                "deployer": deployer,
                "approval_chain": approval_chain,
                "marking_mode": marking_mode,
                "anchor_mode": anchor_mode,
                "configuration": configuration,
                "disclosure_mode": disclosure_mode,
                "ingredients": ingredients,
                **kwargs,
            }
        )
        url = f"{self.base_url}/v1/certify"
        res = self._request_with_x402("POST", url, headers=self._headers(), json=payload)
        res.raise_for_status()
        return res.json()

    def certify_batch(self, items: list[dict[str, Any]], *, watermark: bool = True) -> dict[str, Any]:
        """
        Batch certify up to 100 items.

        Each item should look like the JSON accepted by POST /v1/certify.
        """
        batch_items: list[dict[str, Any]] = []
        for it in items:
            it = dict(it)
            it.setdefault("watermark", watermark)
            batch_items.append(it)

        payload = {"items": batch_items}
        url = f"{self.base_url}/v1/batch"
        res = self._request_with_x402("POST", url, headers=self._headers(), json=payload)
        res.raise_for_status()
        return res.json()

    def verify_certificate(self, id_or_hash: str) -> dict[str, Any]:
        """
        Public verify endpoint (no auth).

        `id_or_hash` can be:
        - a cert id (e.g. vtn_...)
        - or a 64-char content hash
        """
        url = f"{self.base_url}/v1/verify/{id_or_hash}"
        res = self._client.get(url)
        res.raise_for_status()
        return res.json()

    def detect_watermark(self, *, content: str) -> dict[str, Any]:
        """Detect watermark in text (legacy alias — prefer detect())."""
        return self.detect(content=content)

    def detect(
        self,
        *,
        content: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        mime_type: str = "image/png",
        filename: str = "image.png",
    ) -> dict[str, Any]:
        """
        Unified detect (Phase 3): text or image multipart.

        Returns synthid_detected, c2pa_verified, detected_marking_mode, marking_signals, etc.
        """
        url = f"{self.base_url}/v1/detect"
        if content is not None:
            res = self._client.post(url, headers=self._headers(), json={"content": content})
        elif file_bytes is not None:
            res = self._client.post(
                url,
                headers=self._headers(),
                files={"file": (filename, file_bytes, mime_type)},
            )
        else:
            raise ValueError("detect() requires either content or file_bytes")
        res.raise_for_status()
        return res.json()

    def wrap_content(
        self,
        *,
        file_bytes: bytes,
        mime_type: str = "image/png",
        filename: str = "image.png",
        model_id: Optional[str] = None,
        ai_system: Optional[str] = None,
        marking_mode: Optional[str] = None,
        cert_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """C2PA wrap/sign without full certify+anchor (POST /v1/wrap).

        Same auth modes as certify_content: testnet (10 ops/IP), API key, or x402.
        """
        url = f"{self.base_url}/v1/wrap"
        data: dict[str, str] = {}
        if model_id:
            data["model_id"] = model_id
        if ai_system:
            data["ai_system"] = ai_system
        if marking_mode:
            data["marking_mode"] = marking_mode
        if cert_id:
            data["cert_id"] = cert_id
        res = self._request_with_x402(
            "POST",
            url,
            headers=self._headers(),
            files={"file": (filename, file_bytes, mime_type)},
            data=data,
        )
        res.raise_for_status()
        return res.json()

    def get_composition_record(self, cert_id: str) -> dict[str, Any]:
        """Fetch composite ingredient tree (GET /v1/composition/{cert_id}). Public."""
        url = f"{self.base_url}/v1/composition/{cert_id}"
        res = self._client.get(url)
        res.raise_for_status()
        return res.json()

    def get_inclusion_proof(self, cert_id: str) -> dict[str, Any]:
        """Merkle inclusion proof for private anchor (GET /v1/audit/inclusion-proof/{cert_id}). Requires API key."""
        if not self.api_key:
            raise ValueError("api_key is required for get_inclusion_proof()")
        url = f"{self.base_url}/v1/audit/inclusion-proof/{cert_id}"
        res = self._client.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    def get_audit_coverage(
        self,
        *,
        days: int = 30,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """Article 50 coverage matrix (GET /v1/audit/coverage). Requires API key."""
        if not self.api_key:
            raise ValueError("api_key is required for get_audit_coverage()")
        params: dict[str, Any] = {"days": days}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        url = f"{self.base_url}/v1/audit/coverage"
        res = self._client.get(url, headers=self._headers(), params=params)
        res.raise_for_status()
        return res.json()

    def sample_audit(
        self,
        *,
        sample_size: int = 10,
        seed: str = "audit-sample",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        configuration: Optional[str] = None,
        anchor_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        """Reproducible audit sample (POST /v1/audit/sampling). Requires API key."""
        if not self.api_key:
            raise ValueError("api_key is required for sample_audit()")
        payload: dict[str, Any] = {"sample_size": sample_size, "seed": seed}
        if date_from:
            payload["date_from"] = date_from
        if date_to:
            payload["date_to"] = date_to
        if configuration:
            payload["configuration"] = configuration
        if anchor_mode:
            payload["anchor_mode"] = anchor_mode
        url = f"{self.base_url}/v1/audit/sampling"
        res = self._client.post(url, headers=self._headers(), json=payload)
        res.raise_for_status()
        return res.json()

    def audit_export(
        self,
        *,
        format: str = "json",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        configuration: Optional[str] = None,
        anchor_mode: Optional[str] = None,
        include_inclusion_proofs: bool = False,
    ) -> Any:
        """Mode-aware audit export (GET /v1/audit/export). Requires API key."""
        if not self.api_key:
            raise ValueError("api_key is required for audit_export()")
        params: dict[str, Any] = {"format": format}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if configuration:
            params["configuration"] = configuration
        if anchor_mode:
            params["anchor_mode"] = anchor_mode
        if include_inclusion_proofs:
            params["include_inclusion_proofs"] = "true"
        url = f"{self.base_url}/v1/audit/export"
        res = self._client.get(url, headers=self._headers(), params=params)
        res.raise_for_status()
        if format == "json":
            return res.json()
        return res.content

    def get_certificate(self, certificate_id: str) -> dict[str, Any]:
        """
        Authenticated cert lookup.
        Requires X-API-Key (API key only; JWT is not supported by this SDK client).
        """
        if not self.api_key:
            raise ValueError("api_key is required for get_certificate()")
        url = f"{self.base_url}/v1/certs/{certificate_id}"
        res = self._client.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    def list_certificates(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        content_type: Optional[str] = None,
        classification: Optional[str] = None,
        purpose: Optional[str] = None,
        sector: Optional[str] = None,
        distribution_channel: Optional[str] = None,
        language: Optional[str] = None,
        configuration: Optional[str] = None,
        marking_mode: Optional[str] = None,
        anchor_mode: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        format: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Authenticated paginated cert listing.
        """
        if not self.api_key:
            raise ValueError("api_key is required for list_certificates()")
        url = f"{self.base_url}/v1/certs"
        params = _strip_none(
            {
                "offset": offset,
                "limit": limit,
                "content_type": content_type,
                "classification": classification,
                "purpose": purpose,
                "sector": sector,
                "distribution_channel": distribution_channel,
                "language": language,
                "configuration": configuration,
                "marking_mode": marking_mode,
                "anchor_mode": anchor_mode,
                "date_from": date_from,
                "date_to": date_to,
                "format": format,
            }
        )
        res = self._client.get(url, headers=self._headers(), params=params)
        res.raise_for_status()
        return res.json()

    # Simple alias to align with the sprint wording.
    certify = certify_content

