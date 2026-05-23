"""FastAPI app with model warmup during lifespan."""
from contextlib import asynccontextmanager
import logging

import joblib
import numpy as np
from fastapi import FastAPI


MODEL_PATH = "model.joblib"
FEATURE_COUNT = 8
log = logging.getLogger("warmup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = joblib.load(MODEL_PATH)
    dummy = np.zeros((1, FEATURE_COUNT), dtype=np.float32)
    for _ in range(5):
        app.state.model.predict(dummy)
    log.info("warmup complete; first request will be cheap")
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/predict")
def predict(features: list[float]):
    return {"score": float(app.state.model.predict([features])[0])}
