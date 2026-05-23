"""Redis-backed per-tenant counters."""
from __future__ import annotations

import os
import time

import redis


r = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


def check_rate_limit(tenant: str, rpm: int) -> bool:
    """Token bucket: refill rpm/60 per second, capacity rpm."""
    now = time.time()
    key = f"rl:{tenant}"
    p = r.pipeline()
    p.zremrangebyscore(key, 0, now - 60)
    p.zadd(key, {str(now): now})
    p.zcard(key)
    p.expire(key, 65)
    _, _, count, _ = p.execute()
    return count <= rpm


def check_token_quota(tenant: str, monthly: int) -> bool:
    used = int(r.get(f"tokens:{tenant}:month") or 0)
    return used < monthly


def record_tokens(tenant: str, count: int):
    pipe = r.pipeline()
    pipe.incrby(f"tokens:{tenant}:month", count)
    pipe.expire(f"tokens:{tenant}:month", 40 * 24 * 3600)
    pipe.execute()
