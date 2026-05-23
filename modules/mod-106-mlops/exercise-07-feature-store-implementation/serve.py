"""Online serving: read features from Redis with <10ms p99."""
from fastapi import FastAPI
from feast import FeatureStore
from pydantic import BaseModel

app = FastAPI()
fs = FeatureStore(repo_path="feature_repo")


class Req(BaseModel):
    user_id: int


@app.post("/predict")
def predict(req: Req):
    features = fs.get_online_features(
        features=[
            "user_recency:clicks_7d",
            "user_purchase:purchases_30d",
            "user_purchase:ltv",
        ],
        entity_rows=[{"user_id": req.user_id}],
    ).to_dict()
    # Use features for prediction (sketch)
    score = (features["clicks_7d"][0] or 0) * 0.1 + (features["purchases_30d"][0] or 0) * 0.5
    return {"score": score, "features_used": features}
