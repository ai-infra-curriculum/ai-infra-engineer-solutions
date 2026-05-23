"""Point-in-time-correct training join."""
import pandas as pd
from feast import FeatureStore


def main():
    fs = FeatureStore(repo_path="feature_repo")
    # Entity df: each row = (user_id, label_ts). Feast retrieves features as of label_ts.
    entity_df = pd.read_parquet("data/labels.parquet")[["user_id", "event_ts", "label"]]

    training = fs.get_historical_features(
        entity_df=entity_df,
        features=[
            "user_recency:clicks_7d",
            "user_purchase:purchases_30d",
            "user_purchase:ltv",
        ],
    ).to_df()
    training.to_parquet("data/training_features.parquet")
    print(f"wrote training data: {len(training)} rows")


if __name__ == "__main__":
    main()
