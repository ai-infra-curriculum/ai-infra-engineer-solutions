"""Rate limiting via slowapi (per-IP)."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address


def build_limiter(per_min: int) -> Limiter:
    return Limiter(key_func=get_remote_address, default_limits=[f"{per_min}/minute"])
