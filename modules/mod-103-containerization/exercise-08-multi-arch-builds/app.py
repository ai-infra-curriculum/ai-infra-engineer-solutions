"""Trivial iris-api — uses sklearn which has prebuilt wheels for both arches."""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Iris(BaseModel):
    features: list[float]


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/predict")
def predict(req: Iris):
    avg = sum(req.features) / len(req.features)
    label = "setosa" if avg < 3 else "versicolor" if avg < 5 else "virginica"
    return {"label": label}
