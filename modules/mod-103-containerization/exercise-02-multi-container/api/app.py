"""Predict service: writes audit row to Postgres, caches response in Redis."""
from __future__ import annotations

import hashlib
import json
import os

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel

PREDICTIONS = Counter("predictions_total", "Total predictions", ["cached"])
LATENCY = Histogram("prediction_latency_seconds", "Latency (s)")

app = FastAPI()
app.mount("/metrics", make_asgi_app())


class Req(BaseModel):
    features: list[float]


@app.on_event("startup")
async def startup():
    app.state.pg = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    await app.state.pg.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMPTZ DEFAULT NOW(),
            input JSONB NOT NULL,
            output JSONB NOT NULL
        )
    """)
    app.state.redis = await redis.from_url(os.environ["REDIS_URL"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/predict")
async def predict(req: Req):
    with LATENCY.time():
        key = hashlib.sha256(json.dumps(req.features, sort_keys=True).encode()).hexdigest()
        cached = await app.state.redis.get(key)
        if cached:
            PREDICTIONS.labels(cached="true").inc()
            return json.loads(cached)
        result = {"score": sum(req.features) / len(req.features)}
        await app.state.redis.setex(key, 300, json.dumps(result))
        await app.state.pg.execute(
            "INSERT INTO predictions(input, output) VALUES($1, $2)",
            json.dumps(req.features), json.dumps(result),
        )
        PREDICTIONS.labels(cached="false").inc()
        return result
