"""Pattern 4: hot model swap via atomic symlink rename.

Sidecar polls a registry; when a new version is available it downloads to a temp
path and atomically renames `current` to point at it. The serving container
re-reads under a brief lock — no restart, sub-100ms downtime.
"""
from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

import joblib
from fastapi import FastAPI


MODEL_DIR = Path("/models")
CURRENT = MODEL_DIR / "current.joblib"


class HotModel:
    def __init__(self):
        self._lock = threading.RLock()
        self._mtime: float | None = None
        self._model = None
        self._reload()

    def _reload(self):
        with self._lock:
            self._model = joblib.load(CURRENT)
            self._mtime = CURRENT.stat().st_mtime

    def predict(self, features):
        with self._lock:
            if CURRENT.stat().st_mtime != self._mtime:
                self._reload()
            return self._model.predict([features])[0]


app = FastAPI()


@app.on_event("startup")
async def start():
    app.state.hot = HotModel()
    asyncio.create_task(_watcher(app))


async def _watcher(app: FastAPI):
    while True:
        await asyncio.sleep(5)
        if CURRENT.stat().st_mtime != app.state.hot._mtime:
            app.state.hot._reload()


@app.post("/predict")
def predict(features: list[float]):
    return {"score": float(app.state.hot.predict(features))}
