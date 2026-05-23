"""Concurrent benchmark: tokens/s + p50/p95 TTFT."""
import asyncio
import time

import httpx


URL = "http://localhost:8000/v1/completions"
CONCURRENCY = 32
N = 1000


async def one(client, i: int):
    t0 = time.perf_counter()
    r = await client.post(URL, json={
        "model": "mistralai/Mistral-7B-Instruct-v0.2",
        "prompt": f"Write 3 facts about the moon. (request {i})",
        "max_tokens": 100,
    })
    elapsed = time.perf_counter() - t0
    tokens = r.json()["usage"]["completion_tokens"]
    return elapsed, tokens


async def main():
    async with httpx.AsyncClient(timeout=120) as client:
        sem = asyncio.Semaphore(CONCURRENCY)
        async def bounded(i):
            async with sem:
                return await one(client, i)
        t0 = time.perf_counter()
        results = await asyncio.gather(*[bounded(i) for i in range(N)])
        total = time.perf_counter() - t0
    lats = sorted(r[0] for r in results)
    total_tokens = sum(r[1] for r in results)
    print(f"throughput: {total_tokens/total:.1f} tok/s ({N/total:.1f} req/s)")
    print(f"p50 latency: {lats[N//2]:.2f}s  p95: {lats[int(N*0.95)]:.2f}s")


asyncio.run(main())
