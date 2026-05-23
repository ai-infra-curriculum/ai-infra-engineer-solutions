"""Sidecar that aggregates requests into batches before forwarding to the model container."""
import asyncio
import time

import httpx
from fastapi import FastAPI, Request

MAX_BATCH = 32
WINDOW_MS = 20
MODEL_URL = "http://localhost:8001/batch_predict"


queue: asyncio.Queue = asyncio.Queue()


async def batcher():
    async with httpx.AsyncClient() as client:
        while True:
            items = [await queue.get()]
            deadline = time.monotonic() + WINDOW_MS / 1000
            while len(items) < MAX_BATCH:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    items.append(await asyncio.wait_for(queue.get(), remaining))
                except asyncio.TimeoutError:
                    break

            r = await client.post(MODEL_URL, json={"inputs": [it[0] for it in items]})
            for (features, fut), pred in zip(items, r.json()["predictions"]):
                fut.set_result(pred)


app = FastAPI()


@app.on_event("startup")
async def start():
    asyncio.create_task(batcher())


@app.post("/predict")
async def predict(req: Request):
    body = await req.json()
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    await queue.put((body["features"], fut))
    return {"score": await fut}
