"""FastAPI wrapper that picks variant + logs exposure to Kafka."""
from __future__ import annotations

import time

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from assignment import assign


VARIANT_ENDPOINTS = {
    "control": "http://iris-control:8000/predict",
    "treatment": "http://iris-treatment:8000/predict",
}
EXPERIMENT_ID = "iris-rf-v6-test-2026-05"
VARIANTS = {"control": 0.5, "treatment": 0.5}


app = FastAPI()


class Req(BaseModel):
    user_id: int
    features: list[float]


@app.post("/predict")
async def predict(req: Req):
    variant = assign(req.user_id, EXPERIMENT_ID, VARIANTS)
    async with httpx.AsyncClient() as client:
        r = await client.post(VARIANT_ENDPOINTS[variant], json=req.dict())
    # Exposure log: would publish to Kafka in prod
    log_exposure(EXPERIMENT_ID, req.user_id, variant, r.json())
    return {"variant": variant, **r.json()}


def log_exposure(experiment_id: str, user_id: int, variant: str, response: dict):
    print({"ts": time.time(), "experiment_id": experiment_id,
            "user_id": user_id, "variant": variant, "response": response})
