"""Stage 2: preprocess (split + scale)."""
from pathlib import Path

import pandas as pd
import yaml
from joblib import dump
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def main():
    params = yaml.safe_load(open("params.yaml"))["preprocess"]
    Path("data/processed").mkdir(parents=True, exist_ok=True)

    df = pd.read_csv("data/raw/iris.csv")
    X, y = df.drop(columns="target"), df["target"]
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=params["test_size"], random_state=params["random_seed"], stratify=y,
    )
    scaler = StandardScaler().fit(Xtr)
    pd.DataFrame(scaler.transform(Xtr), columns=X.columns).to_parquet("data/processed/X_train.parquet")
    pd.DataFrame(scaler.transform(Xte), columns=X.columns).to_parquet("data/processed/X_test.parquet")
    ytr.to_frame("target").to_parquet("data/processed/y_train.parquet")
    yte.to_frame("target").to_parquet("data/processed/y_test.parquet")
    dump(scaler, "data/processed/scaler.joblib")


if __name__ == "__main__":
    main()
