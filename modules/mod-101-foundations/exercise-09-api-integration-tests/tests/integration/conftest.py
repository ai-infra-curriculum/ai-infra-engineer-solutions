"""Integration fixture: spin up real container via testcontainers."""
import os
import time

import pytest
import requests


@pytest.fixture(scope="session")
def real_api_url():
    """Assumes the model-serve container is already running at MODEL_SERVE_URL.

    In CI, start via docker-compose before pytest runs.
    """
    url = os.environ.get("MODEL_SERVE_URL", "http://localhost:8000")
    # Wait for health
    for _ in range(30):
        try:
            if requests.get(f"{url}/health", timeout=2).status_code == 200:
                return url
        except Exception:
            pass
        time.sleep(1)
    pytest.skip("model-serve not reachable at " + url)
