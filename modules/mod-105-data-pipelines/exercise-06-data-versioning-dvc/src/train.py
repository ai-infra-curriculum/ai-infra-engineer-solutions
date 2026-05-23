"""Stage 3: train."""
from pathlib import Path

import pandas as pd
import yaml
from joblib import dump
from sklearn.ensemble import RandomForestClassifier


def main():
    params = yaml.safe_load(open("params.yaml"))["train"]
    Path("models").mkdir(exist_ok=True)

    X = pd.read_parquet("data/processed/X_train.parquet")
    y = pd.read_parquet("data/processed/y_train.parquet")["target"]
    model = RandomForestClassifier(
        n_estimators=params["n_estimators"],
        max_depth=params["max_depth"],
        min_samples_leaf=params["min_samples_leaf"],
        random_state=0,
    ).fit(X, y)
    dump(model, "models/model.pkl")


if __name__ == "__main__":
    main()
