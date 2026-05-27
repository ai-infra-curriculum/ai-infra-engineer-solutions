"""
Response Cache for LLM API Gateway

LRU-backed cache for completion responses, keyed on the
(model, prompt, temperature, max_tokens) tuple. Temperature == 0
responses are deterministic so caching them is safe; any non-zero
temperature is treated as non-cacheable by default.

Includes hit/miss accounting + a periodic eviction sweep for stale
entries based on a configurable TTL.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """One cached completion."""

    key: str
    response: str
    model: str
    created_at: datetime
    last_accessed_at: datetime
    hit_count: int = 0
    tokens_used: int = 0


@dataclass
class CacheStats:
    """Snapshot of cache hit/miss/eviction counters."""

    hits: int = 0
    misses: int = 0
    evictions_capacity: int = 0
    evictions_ttl: int = 0
    inserts: int = 0

    @property
    def total_lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate_percent(self) -> float:
        total = self.total_lookups
        return (self.hits / total * 100.0) if total else 0.0


def cache_key(
    *,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    user_id: Optional[str] = None,
) -> str:
    """Deterministic key for an LLM request."""
    parts = [model, prompt, f"t={temperature:.4f}", f"max={max_tokens}",
             f"u={user_id or ''}"]
    digest = hashlib.sha256("\n".join(parts).encode()).hexdigest()
    return f"llm:{model}:{digest[:32]}"


class ResponseCache:
    """Thread-safe LRU response cache with TTL + cacheability rules."""

    def __init__(
        self,
        *,
        max_entries: int = 1000,
        ttl_seconds: int = 3600,
        max_cacheable_temperature: float = 0.001,
    ):
        self.max_entries = max_entries
        self.ttl = timedelta(seconds=ttl_seconds)
        self.max_cacheable_temperature = max_cacheable_temperature
        self._entries: "OrderedDict[str, CacheEntry]" = OrderedDict()
        self._lock = threading.RLock()
        self.stats = CacheStats()

    def get(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        user_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[str]:
        if temperature > self.max_cacheable_temperature:
            self.stats.misses += 1
            return None
        now = now or datetime.now(timezone.utc)
        key = cache_key(
            model=model, prompt=prompt, temperature=temperature,
            max_tokens=max_tokens, user_id=user_id,
        )
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.stats.misses += 1
                return None
            if now - entry.created_at > self.ttl:
                # Expired: drop + treat as miss.
                self._entries.pop(key, None)
                self.stats.evictions_ttl += 1
                self.stats.misses += 1
                return None
            self._entries.move_to_end(key)
            entry.last_accessed_at = now
            entry.hit_count += 1
            self.stats.hits += 1
            return entry.response

    def put(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        response: str,
        tokens_used: int = 0,
        user_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[CacheEntry]:
        if temperature > self.max_cacheable_temperature:
            return None
        now = now or datetime.now(timezone.utc)
        key = cache_key(
            model=model, prompt=prompt, temperature=temperature,
            max_tokens=max_tokens, user_id=user_id,
        )
        entry = CacheEntry(
            key=key, response=response, model=model,
            created_at=now, last_accessed_at=now,
            tokens_used=tokens_used,
        )
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                self._entries[key] = entry
            else:
                if len(self._entries) >= self.max_entries:
                    self._entries.popitem(last=False)
                    self.stats.evictions_capacity += 1
                self._entries[key] = entry
            self.stats.inserts += 1
        return entry

    def sweep_expired(self, *, now: Optional[datetime] = None) -> int:
        """Remove expired entries; returns the count removed."""
        now = now or datetime.now(timezone.utc)
        removed = 0
        with self._lock:
            for key in list(self._entries.keys()):
                entry = self._entries[key]
                if now - entry.created_at > self.ttl:
                    self._entries.pop(key)
                    removed += 1
                    self.stats.evictions_ttl += 1
        return removed

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
