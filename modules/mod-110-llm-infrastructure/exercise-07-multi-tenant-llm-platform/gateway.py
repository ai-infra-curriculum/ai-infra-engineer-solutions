"""Multi-tenant LLM gateway."""
from __future__ import annotations

import hashlib
import time

import httpx
import yaml
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

import usage_store


tenants = {t["api_key_hash"]: t for t in yaml.safe_load(open("tenants.yaml"))["tenants"]}
app = FastAPI()


def hash_key(k: str) -> str:
    return hashlib.sha256(k.encode()).hexdigest()


def auth(api_key: str) -> dict:
    t = tenants.get(hash_key(api_key))
    if not t:
        raise HTTPException(401, "invalid api key")
    return t


class ChatReq(BaseModel):
    model: str
    prompt: str
    max_tokens: int = 200


@app.post("/v1/chat")
async def chat(req: ChatReq, x_api_key: str = Header(...)):
    tenant = auth(x_api_key)
    tid = tenant["id"]

    if not usage_store.check_rate_limit(tid, tenant["rpm_limit"]):
        raise HTTPException(429, "rate limit exceeded")

    if not usage_store.check_token_quota(tid, tenant["monthly_token_budget"]):
        raise HTTPException(429, "monthly token quota exhausted")

    if req.model not in tenant["allowed_models"]:
        raise HTTPException(403, f"model {req.model} not allowed for tenant")

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"http://vllm:8000/v1/completions",
            json={"model": req.model, "prompt": req.prompt, "max_tokens": req.max_tokens},
        )
    body = r.json()
    used = body["usage"]["total_tokens"]
    usage_store.record_tokens(tid, used)
    return body
