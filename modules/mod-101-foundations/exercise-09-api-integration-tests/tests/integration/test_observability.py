"""Integration: real HTTP traffic, real container."""
import pytest
import requests


pytestmark = pytest.mark.integration


def test_metrics_exposed(real_api_url):
    r = requests.get(f"{real_api_url}/metrics")
    assert r.status_code == 200
    for marker in (b"predictions_total", b"http_request_duration"):
        assert marker in r.content


def test_request_id_propagated(real_api_url):
    rid = "integration-test-rid-abc"
    r = requests.get(f"{real_api_url}/health", headers={"X-Request-Id": rid})
    assert r.headers["x-request-id"] == rid


def test_predict_end_to_end(real_api_url):
    r = requests.post(f"{real_api_url}/v1/predict",
                       json={"features": [5.1, 3.5, 1.4, 0.2]})
    assert r.status_code == 200
    assert "prediction" in r.json()
