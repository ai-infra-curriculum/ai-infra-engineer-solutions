"""Pydantic input/output schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    features: list[float] = Field(..., min_length=1, max_length=1024)
    model_version: str = "latest"


class PredictResponse(BaseModel):
    prediction: float
    model_version: str
    latency_ms: float


class BatchItem(BaseModel):
    features: list[float] = Field(..., min_length=1, max_length=1024)


class BatchRequest(BaseModel):
    items: list[BatchItem] = Field(..., min_length=1, max_length=128)


class BatchResponse(BaseModel):
    predictions: list[PredictResponse]
