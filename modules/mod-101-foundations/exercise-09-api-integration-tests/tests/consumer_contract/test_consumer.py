"""Consumer-driven contract via Pact.

In a real workflow:
  1. This file (consumer) generates a pact contract.
  2. The contract is published.
  3. The provider (model-serve) is verified against it in its own CI.
"""
import pytest
from pact import Consumer, Provider


pytestmark = pytest.mark.consumer_contract


@pytest.fixture(scope="module")
def pact():
    p = Consumer("dashboard").has_pact_with(Provider("model-serve"))
    p.start_service()
    yield p
    p.stop_service()


def test_predict_contract(pact):
    expected_body = {
        "prediction": 0.0,
        "model_version": "v1",
        "latency_ms": 0.0,
    }

    (pact
        .given("model is loaded")
        .upon_receiving("a valid predict request")
        .with_request("POST", "/v1/predict",
                      body={"features": [1.0, 0.0, 0.0, 0.0]},
                      headers={"Content-Type": "application/json"})
        .will_respond_with(200, body=expected_body))

    with pact:
        # The consumer would call here using pact.uri as the base URL
        pass
