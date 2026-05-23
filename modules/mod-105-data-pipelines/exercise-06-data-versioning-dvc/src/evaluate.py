"""Stage 4: evaluate. Writes metrics + plots."""
import json
from pathlib import Path

import pandas as pd
from joblib import load
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score


def main():
    Path("metrics").mkdir(exist_ok=True)
    Path("plots").mkdir(exist_ok=True)

    model = load("models/model.pkl")
    X = pd.read_parquet("data/processed/X_test.parquet")
    y = pd.read_parquet("data/processed/y_test.parquet")["target"]
    preds = model.predict(X)

    metrics = {
        "accuracy": float(accuracy_score(y, preds)),
        "f1_macro": float(f1_score(y, preds, average="macro")),
    }
    with open("metrics/eval.json", "w") as f:
        json.dump(metrics, f, indent=2)

    cm = confusion_matrix(y, preds).tolist()
    with open("plots/confusion-matrix.json", "w") as f:
        json.dump({"matrix": cm}, f)
    print(metrics)


if __name__ == "__main__":
    main()
