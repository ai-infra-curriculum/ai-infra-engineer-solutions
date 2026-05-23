"""Inference handler usable on SageMaker (SKLearn container), Vertex (custom container), Azure ML.

For SageMaker SKLearn container, this file must define model_fn, input_fn, predict_fn, output_fn.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib


def model_fn(model_dir: str):
    """SageMaker: load the model from the artifact directory."""
    return joblib.load(Path(model_dir) / "model.joblib")


def input_fn(request_body, content_type="application/json"):
    return json.loads(request_body)["features"]


def predict_fn(features, model):
    return int(model.predict([features])[0])


def output_fn(prediction, accept="application/json"):
    return json.dumps({"prediction": prediction})
