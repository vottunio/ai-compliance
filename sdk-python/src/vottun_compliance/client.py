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

    Testnet/free mode:
    - leave `api_key` as None and do not send any X-API-Key header.

    Mainnet/paid mode:
    - provide `api_key` and the client will send `X-API-Key`.
    """

    base_url: str = DEFAULT_BASE_URL
    api_key: Optional[str] = None
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

    def certify_content(
        self,
        *,
        content: Optional[str] = None,
        content_hash: Optional[str] = None,
        ai_system: Optional[str] = None,
        model_id: Optional[str] = None,
        watermark: bool = True,
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
                **kwargs,
            }
        )
        url = f"{self.base_url}/v1/certify"
        res = self._client.post(url, headers=self._headers(), json=payload)
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
        res = self._client.post(url, headers=self._headers(), json=payload)
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
        """Public watermark detect endpoint (no auth)."""
        url = f"{self.base_url}/v1/detect"
        res = self._client.post(url, headers=self._headers(), json={"content": content})
        res.raise_for_status()
        return res.json()

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
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
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
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        res = self._client.get(url, headers=self._headers(), params=params)
        res.raise_for_status()
        return res.json()

    # Simple alias to align with the sprint wording.
    certify = certify_content

