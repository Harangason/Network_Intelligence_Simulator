from __future__ import annotations

import hashlib


def stable_seed(seed: int, *parts: object) -> int:
    digest = hashlib.sha256(":".join([str(seed), *(str(part) for part in parts)]).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")
