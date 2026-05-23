"""Middleware that records LLM-specific metrics around vLLM client."""
import time
from contextlib import asynccontextmanager

from metrics import (TTFT, TOKEN_THROUGHPUT, PROMPT_LENGTH, COMPLETION_LENGTH,
                      MODEL_USE, ACTIVE_STREAMS)


@asynccontextmanager
async def instrument(model: str, tenant: str, prompt_tokens: int):
    PROMPT_LENGTH.labels(model=model, tenant=tenant).observe(prompt_tokens)
    MODEL_USE.labels(model=model, tenant=tenant, tier="medium").inc()
    ACTIVE_STREAMS.labels(model=model).inc()
    t0 = time.perf_counter()
    first_token_t = None
    total_tokens = 0

    async def yielded(token: str):
        nonlocal first_token_t, total_tokens
        if first_token_t is None:
            first_token_t = time.perf_counter()
            TTFT.labels(model=model, tenant=tenant).observe(first_token_t - t0)
        total_tokens += 1

    try:
        yield yielded
    finally:
        elapsed = time.perf_counter() - t0
        if first_token_t and total_tokens > 0:
            stream_elapsed = time.perf_counter() - first_token_t
            if stream_elapsed > 0:
                TOKEN_THROUGHPUT.labels(model=model, tenant=tenant).observe(total_tokens / stream_elapsed)
        COMPLETION_LENGTH.labels(model=model, tenant=tenant).observe(total_tokens)
        ACTIVE_STREAMS.labels(model=model).dec()
