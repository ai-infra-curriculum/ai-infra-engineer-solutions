"""Unit tests: pure functions, no IO."""
import pytest

from model_serve.ml.schemas import BatchRequest, PredictRequest


pytestmark = pytest.mark.unit


def test_predict_request_accepts_valid_features():
    req = PredictRequest(features=[1.0, 2.0, 3.0])
    assert len(req.features) == 3


def test_predict_request_rejects_empty():
    with pytest.raises(Exception):
        PredictRequest(features=[])


def test_predict_request_rejects_too_many():
    with pytest.raises(Exception):
        PredictRequest(features=[1.0] * 2000)


def test_batch_request_limits_items():
    items = [{"features": [1.0]} for _ in range(200)]
    with pytest.raises(Exception):
        BatchRequest(items=items)


def test_default_model_version():
    req = PredictRequest(features=[1.0])
    assert req.model_version == "latest"
