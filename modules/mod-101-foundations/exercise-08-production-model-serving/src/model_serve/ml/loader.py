"""Thread-safe model loader."""
from __future__ import annotations

import logging
from threading import Lock

import joblib


_log = logging.getLogger(__name__)
_lock = Lock()
_state: dict = {"model": None, "version": None, "path": None}


def load(path: str, version: str) -> None:
    with _lock:
        _log.info("loading model %s from %s", version, path)
        _state["model"] = joblib.load(path)
        _state["version"] = version
        _state["path"] = path


def reload(path: str | None = None, version: str | None = None) -> None:
    with _lock:
        p = path or _state["path"]
        v = version or _state["version"]
        _state["model"] = joblib.load(p)
        _state["version"] = v


def get_model():
    return _state["model"]


def get_version() -> str | None:
    return _state["version"]


def is_loaded() -> bool:
    return _state["model"] is not None
