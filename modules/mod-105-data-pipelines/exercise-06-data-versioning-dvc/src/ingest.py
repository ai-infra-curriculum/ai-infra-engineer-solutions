"""Stage 1: ingest. Pulls Iris CSV; would pull from S3/db in production."""
from pathlib import Path

import pandas as pd
from sklearn.datasets import load_iris


def main():
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    iris = load_iris(as_frame=True)
    df = iris.frame
    df.to_csv("data/raw/iris.csv", index=False)
    print(f"wrote {len(df)} rows")


if __name__ == "__main__":
    main()
