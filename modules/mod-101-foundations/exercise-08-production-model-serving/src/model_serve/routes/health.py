"""Liveness + readiness probes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..ml import loader


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict:
    if not loader.is_loaded():
        raise HTTPException(status_code=503, detail="model not loaded")
    return {"status": "ready", "model_version": loader.get_version()}
