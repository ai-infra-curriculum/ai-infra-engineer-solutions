"""Contract tests covering all 15 requirements."""


def test_health_always_ok(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_ready_returns_200_after_lifespan_loads(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["model_version"]


def test_predict_happy_path(client):
    r = client.post("/v1/predict", json={"features": [1.0, 0.0, 0.0, 0.0]})
    assert r.status_code == 200
    body = r.json()
    assert "prediction" in body
    assert body["latency_ms"] >= 0


def test_predict_wrong_feature_count(client):
    r = client.post("/v1/predict", json={"features": [1.0]})
    assert r.status_code == 400


def test_predict_validation_missing_features(client):
    r = client.post("/v1/predict", json={})
    assert r.status_code == 422


def test_batch_happy_path(client):
    r = client.post("/v1/predict/batch",
                     json={"items": [{"features": [1.0, 0.0, 0.0, 0.0]},
                                       {"features": [0.0, 1.0, 0.0, 0.0]}]})
    assert r.status_code == 200
    assert len(r.json()["predictions"]) == 2


def test_batch_over_limit(client):
    items = [{"features": [1.0, 0.0, 0.0, 0.0]}] * 200
    r = client.post("/v1/predict/batch", json={"items": items})
    assert r.status_code == 422   # caught by Pydantic max_length


def test_list_models(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    assert r.json()["current"]["version"]


def test_admin_requires_token(client):
    r = client.post("/v1/admin/reload")
    assert r.status_code == 401


def test_admin_with_token(client):
    r = client.post("/v1/admin/reload", headers={"x-admin-token": "change-me"})
    assert r.status_code == 200


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"predictions_total" in r.content or b"http_requests_total" in r.content


def test_request_id_passthrough(client):
    rid = "test-id-abc"
    r = client.get("/health", headers={"x-request-id": rid})
    assert r.headers["x-request-id"] == rid


def test_request_id_generated_if_missing(client):
    r = client.get("/health")
    assert r.headers.get("x-request-id")
