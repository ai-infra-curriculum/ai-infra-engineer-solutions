"""/v1/predict + /v1/predict/batch + /v1/models."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request

from ..config import Settings
from ..instrumentation import INFLIGHT, MODEL_INFO, PREDICT_LATENCY, PREDICTIONS
from ..ml import loader
from ..ml.schemas import BatchRequest, BatchResponse, PredictRequest, PredictResponse


router = APIRouter(prefix="/v1")


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, request: Request) -> PredictResponse:
    settings = _settings(request)
    if len(req.features) != settings.feature_count:
        raise HTTPException(400, f"features must have length {settings.feature_count}")

    INFLIGHT.inc()
    try:
        t0 = time.perf_counter()
        pred = float(loader.get_model().predict([req.features])[0])
        elapsed = time.perf_counter() - t0
        PREDICT_LATENCY.observe(elapsed)
        version = loader.get_version() or "unknown"
        PREDICTIONS.labels(status="ok", model_version=version).inc()
        return PredictResponse(prediction=pred, model_version=version,
                                latency_ms=round(elapsed * 1000, 3))
    except Exception:
        PREDICTIONS.labels(status="error", model_version=loader.get_version() or "unknown").inc()
        raise
    finally:
        INFLIGHT.dec()


@router.post("/predict/batch", response_model=BatchResponse)
def predict_batch(req: BatchRequest, request: Request) -> BatchResponse:
    settings = _settings(request)
    expected = settings.feature_count

    rows = []
    for item in req.items:
        if len(item.features) != expected:
            raise HTTPException(400, f"every item must have features of length {expected}")
        rows.append(item.features)

    INFLIGHT.inc()
    try:
        t0 = time.perf_counter()
        preds = loader.get_model().predict(rows)
        elapsed = time.perf_counter() - t0
        PREDICT_LATENCY.observe(elapsed)
        version = loader.get_version() or "unknown"
        per_item_ms = round(elapsed * 1000 / len(rows), 3)

        responses = [
            PredictResponse(prediction=float(p), model_version=version, latency_ms=per_item_ms)
            for p in preds
        ]
        PREDICTIONS.labels(status="ok", model_version=version).inc(len(rows))
        return BatchResponse(predictions=responses)
    finally:
        INFLIGHT.dec()


@router.get("/models")
def list_models() -> dict:
    if not loader.is_loaded():
        raise HTTPException(503, "model not loaded")
    return {"current": {"version": loader.get_version()}}
