"""Test fixtures: in-process FastAPI test client + tiny in-memory model."""
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(scope="session")
def model_path(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("model")
    model = LinearRegression().fit(np.eye(4), np.arange(4, dtype=float))
    path = tmp / "model.joblib"
    joblib.dump(model, path)
    return str(path)


@pytest.fixture
def client(model_path, monkeypatch):
    monkeypatch.setenv("MODEL_SERVE_MODEL_PATH", model_path)
    monkeypatch.setenv("MODEL_SERVE_FEATURE_COUNT", "4")
    monkeypatch.setenv("MODEL_SERVE_RATE_LIMIT_PER_MIN", "10000")
    # Reset loader state in case previous test loaded
    from model_serve.ml import loader
    loader._state["model"] = None

    from model_serve.app import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c
