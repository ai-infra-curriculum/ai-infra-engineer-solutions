"""Concurrent query benchmark."""
import argparse
import asyncio
import time

import numpy as np


DIM = 384


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("db", choices=["qdrant", "pgvector"])
    p.add_argument("--n", type=int, default=10_000)
    p.add_argument("--concurrency", type=int, default=32)
    args = p.parse_args()

    queries = np.random.randn(args.n, DIM).astype(np.float32)

    if args.db == "qdrant":
        from qdrant_client import QdrantClient
        c = QdrantClient(host="localhost", port=6333)
        async def search(q):
            await asyncio.to_thread(c.search, "bench", q.tolist(), limit=10)
    else:
        import psycopg
        pool = psycopg.AsyncConnection.connect_async("postgresql://postgres@localhost/postgres")
        conn = await pool
        async def search(q):
            await conn.execute("SELECT id FROM bench ORDER BY embedding <=> %s LIMIT 10", (q.tolist(),))

    sem = asyncio.Semaphore(args.concurrency)
    lats = []
    async def bounded(q):
        async with sem:
            t0 = time.perf_counter()
            await search(q)
            lats.append(time.perf_counter() - t0)

    t0 = time.perf_counter()
    await asyncio.gather(*[bounded(q) for q in queries])
    total = time.perf_counter() - t0

    lats.sort()
    print(f"{args.db}: qps={args.n/total:.0f}  p50={lats[args.n//2]*1000:.1f}ms  "
          f"p95={lats[int(args.n*0.95)]*1000:.1f}ms")


asyncio.run(main())
