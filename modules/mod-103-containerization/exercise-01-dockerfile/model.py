"""ResNet50 image classifier."""
from __future__ import annotations

from functools import lru_cache

import torch
from PIL import Image
from torchvision.models import resnet50, ResNet50_Weights


@lru_cache(maxsize=1)
def get_model():
    weights = ResNet50_Weights.DEFAULT
    model = resnet50(weights=weights)
    model.train(False)
    return model, weights


def classify(img: Image.Image, top_k: int = 3) -> list[dict]:
    model, weights = get_model()
    preprocess = weights.transforms()
    batch = preprocess(img).unsqueeze(0)
    with torch.inference_mode():
        out = model(batch).softmax(dim=1)
    probs, idxs = out.topk(top_k)
    return [
        {"label": weights.meta["categories"][i], "score": float(p)}
        for p, i in zip(probs[0], idxs[0])
    ]
