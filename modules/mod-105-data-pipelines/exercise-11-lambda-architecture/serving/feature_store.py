"""Feature store: merge batch (S3 Parquet, ~24h fresh) + stream (Redis, <1min)."""
from __future__ import annotations

import json

import pandas as pd
import redis


class FeatureStore:
    def __init__(self, batch_parquet: str, redis_url: str):
        self.batch = pd.read_parquet(batch_parquet).set_index("user_id")
        self.r = redis.from_url(redis_url)

    def get(self, user_id: int) -> dict:
        # Batch: all-time features
        if user_id in self.batch.index:
            features = self.batch.loc[user_id].to_dict()
        else:
            features = {"clicks_30d": 0, "purchases_30d": 0, "revenue_30d": 0, "sessions_30d": 0}

        # Stream: recent (last 5 minutes)
        recent = self.r.hgetall(f"features:{user_id}")
        if recent:
            features["clicks_5m"] = int(recent.get(b"clicks_5m", 0))
            features["last_event_ts"] = recent.get(b"last_event_ts", b"").decode()

        return features
