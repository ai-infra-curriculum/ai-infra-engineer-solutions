"""Frontend driver: emits requests across the chain."""
from __future__ import annotations

import asyncio
import logging
import random

import httpx

from otel_setup import setup


tracer = setup("frontend")
log = logging.getLogger("frontend")


async def main():
    async with httpx.AsyncClient() as client:
        for _ in range(20):
            user_id = random.randint(0, 100)
            with tracer.start_as_current_span("client_request") as span:
                span.set_attribute("user.id", user_id)
                r = await client.get(f"http://backend:8000/predict/{user_id}")
                log.info("got response", extra={"status": r.status_code})


if __name__ == "__main__":
    asyncio.run(main())
