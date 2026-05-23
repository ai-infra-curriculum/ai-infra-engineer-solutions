"""Bulk-insert N random 384-dim vectors into the chosen DB."""
from __future__ import annotations

import argparse
import time

import numpy as np


DIM = 384


def load_qdrant(n: int):
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams, PointStruct

    c = QdrantClient(host="localhost", port=6333)
    c.recreate_collection("bench", VectorParams(size=DIM, distance=Distance.COSINE))

    batch = 10_000
    t0 = time.perf_counter()
    for start in range(0, n, batch):
        vecs = np.random.randn(batch, DIM).astype(np.float32)
        points = [PointStruct(id=start + i, vector=v.tolist()) for i, v in enumerate(vecs)]
        c.upsert("bench", points=points)
    print(f"qdrant: loaded {n} in {time.perf_counter() - t0:.1f}s")


def load_pgvector(n: int):
    import psycopg
    conn = psycopg.connect("postgresql://postgres@localhost/postgres")
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute("DROP TABLE IF EXISTS bench")
    conn.execute(f"CREATE TABLE bench (id bigint primary key, embedding vector({DIM}))")
    conn.execute("CREATE INDEX ON bench USING hnsw (embedding vector_cosine_ops)")
    batch = 5000
    t0 = time.perf_counter()
    for start in range(0, n, batch):
        vecs = np.random.randn(batch, DIM).astype(np.float32)
        rows = [(start + i, v.tolist()) for i, v in enumerate(vecs)]
        conn.executemany("INSERT INTO bench VALUES (%s, %s)", rows)
    conn.commit()
    print(f"pgvector: loaded {n} in {time.perf_counter() - t0:.1f}s")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("db", choices=["qdrant", "pgvector", "weaviate"])
    p.add_argument("--n", type=int, default=1_000_000)
    args = p.parse_args()
    {"qdrant": load_qdrant, "pgvector": load_pgvector}[args.db](args.n)


if __name__ == "__main__":
    main()
