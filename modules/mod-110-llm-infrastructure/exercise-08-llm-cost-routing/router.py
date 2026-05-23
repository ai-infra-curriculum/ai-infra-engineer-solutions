"""Routing layer with cost-aware tier selection + confidence escalation."""
from __future__ import annotations

import os

import httpx
import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from classifier import classify


cfg = yaml.safe_load(open("tiers.yaml"))
TIERS = cfg["tiers"]
CONF_THRESHOLD = cfg["confidence_threshold"]
TIER_ORDER = ["small", "medium", "large"]


app = FastAPI()


class Req(BaseModel):
    prompt: str


async def call_tier(tier: str, prompt: str) -> tuple[str, float]:
    t = TIERS[tier]
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(t["endpoint"], json={
            "model": t["model"], "prompt": prompt, "max_tokens": 500, "logprobs": 5,
        })
    body = r.json()
    text = body["choices"][0]["text"]
    # Confidence approximation: average log-prob of top tokens
    logprobs = body["choices"][0].get("logprobs", {}).get("token_logprobs", [-1])
    confidence = min(1.0, max(0.0, sum(logprobs) / len(logprobs) + 1.0))
    return text, confidence


@app.post("/v1/route")
async def route(req: Req):
    tier = classify(req.prompt)
    response, conf = await call_tier(tier, req.prompt)
    while conf < CONF_THRESHOLD and TIER_ORDER.index(tier) < len(TIER_ORDER) - 1:
        tier = TIER_ORDER[TIER_ORDER.index(tier) + 1]
        response, conf = await call_tier(tier, req.prompt)

    return {"tier_used": tier, "confidence": conf, "response": response}
