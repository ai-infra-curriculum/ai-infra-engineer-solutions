"""FastAPI ResNet image classifier."""
from __future__ import annotations

import io

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image

from model import classify, get_model

app = FastAPI(title="resnet-classifier")


@app.on_event("startup")
def warmup():
    get_model()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        img = Image.open(io.BytesIO(await file.read())).convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"invalid image: {e}")
    return {"predictions": classify(img)}
