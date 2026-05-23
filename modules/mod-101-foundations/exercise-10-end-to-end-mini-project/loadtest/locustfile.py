"""Locust smoke load for the mini-platform."""
import random

from locust import HttpUser, between, task


class IrisUser(HttpUser):
    wait_time = between(0.05, 0.30)

    @task(10)
    def predict(self):
        self.client.post("/v1/predict", json={
            "features": [round(random.uniform(4, 8), 1),
                          round(random.uniform(2, 5), 1),
                          round(random.uniform(1, 7), 1),
                          round(random.uniform(0.1, 2.5), 1)],
        }, name="POST /v1/predict")

    @task(1)
    def health(self):
        self.client.get("/health", name="GET /health")
