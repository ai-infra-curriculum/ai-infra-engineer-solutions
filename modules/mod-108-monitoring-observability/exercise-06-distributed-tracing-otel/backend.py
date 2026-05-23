"""Backend: fetches features + runs inference."""
from __future__ import annotations

import time

import httpx
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from otel_setup import setup


tracer = setup("backend")
app = FastAPI()
FastAPIInstrumentor.instrument_app(app)

FEATURE_STORE = "http://feature-store:8000"


@app.get("/predict/{user_id}")
async def predict(user_id: int):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{FEATURE_STORE}/features/{user_id}")
    with tracer.start_as_current_span("model_inference") as span:
        time.sleep(0.04)
        span.set_attribute("model.version", "v3")
        return {"user_id": user_id, "score": sum(r.json()["features"])}
