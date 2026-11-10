"""RFC 6962 / RFC 9162 inclusion proof verification. Same algorithm as the backend."""
from __future__ import annotations

from typing import List

from .canonical import node_hash


def verify_inclusion(leaf: bytes, index: int, size: int, path: List[bytes], root: bytes) -> bool:
    """True if `leaf` (a leaf hash) is at `index` in the tree of `size` leaves with `root`."""
    if not 0 <= index < size:
        return False
    fn, sn = index, size - 1
    r = leaf
    for p in path:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = node_hash(p, r)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root
