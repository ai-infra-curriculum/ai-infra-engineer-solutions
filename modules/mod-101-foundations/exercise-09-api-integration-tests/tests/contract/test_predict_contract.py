"""Contract tests: in-process FastAPI client."""
import os

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression


pytestmark = pytest.mark.contract


@pytest.fixture(scope="module")
def model_path(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("contract-model")
    m = LinearRegression().fit(np.eye(4), np.arange(4, dtype=float))
    p = tmp / "model.joblib"
    joblib.dump(m, p)
    return str(p)


@pytest.fixture
def client(model_path, monkeypatch):
    monkeypatch.setenv("MODEL_SERVE_MODEL_PATH", model_path)
    monkeypatch.setenv("MODEL_SERVE_FEATURE_COUNT", "4")
    monkeypatch.setenv("MODEL_SERVE_RATE_LIMIT_PER_MIN", "10000")
    from model_serve.ml import loader
    loader._state["model"] = None
    from model_serve.app import create_app
    with TestClient(create_app()) as c:
        yield c


def test_predict_returns_expected_shape(client):
    r = client.post("/v1/predict", json={"features": [1.0, 0.0, 0.0, 0.0]})
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"prediction", "model_version", "latency_ms"}


def test_predict_validation_errors_field_level(client):
    r = client.post("/v1/predict", json={"features": "not a list"})
    assert r.status_code == 422
    assert "detail" in r.json()


def test_health_no_body_required(client):
    assert client.get("/health").status_code == 200


def test_metrics_exposed_for_scraping(client):
    r = client.get("/metrics")
    assert r.status_code == 200
