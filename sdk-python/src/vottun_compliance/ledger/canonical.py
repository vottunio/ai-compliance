"""Canonical JSON and RFC 6962 hashes for the AI Ledger (format v1). Same bytes as the backend."""
from __future__ import annotations

import hashlib
import json
from typing import Any

_LEAF_PREFIX = b"\x00"
_NODE_PREFIX = b"\x01"


def _reject_floats(value: Any, path: str = "$") -> None:
    """Raise ValueError if any decimal appears anywhere in the structure."""
    if isinstance(value, float):
        raise ValueError("decimals are not allowed in canonical JSON (at %s)" % path)
    if isinstance(value, dict):
        for k, v in value.items():
            _reject_floats(v, "%s.%s" % (path, k))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _reject_floats(v, "%s[%d]" % (path, i))


def canonical_bytes(obj: Any) -> bytes:
    """Sorted keys, no spaces, UTF-8, non-ASCII unescaped; rejects decimals."""
    _reject_floats(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def leaf_hash(data: bytes) -> bytes:
    """SHA-256(0x00 || data)."""
    return hashlib.sha256(_LEAF_PREFIX + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    """SHA-256(0x01 || left || right)."""
    return hashlib.sha256(_NODE_PREFIX + left + right).digest()
