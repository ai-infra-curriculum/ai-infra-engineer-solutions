"""Feature store: returns features (with synthetic slow path)."""
from __future__ import annotations

import random
import time

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from otel_setup import setup


tracer = setup("feature-store")
app = FastAPI()
FastAPIInstrumentor.instrument_app(app)


@app.get("/features/{user_id}")
def features(user_id: int):
    with tracer.start_as_current_span("feature_lookup") as span:
        span.set_attribute("user.id", user_id)
        # Synthetic slow scenario: every 10th call is slow
        if user_id % 10 == 0:
            with tracer.start_as_current_span("slow_table_scan"):
                time.sleep(0.3)
                span.set_attribute("slow", True)
        return {"features": [random.random() for _ in range(8)]}
