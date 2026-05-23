"""Materialize features from offline → online (Redis)."""
from datetime import datetime, timedelta

from feast import FeatureStore


def main():
    fs = FeatureStore(repo_path="feature_repo")
    end = datetime.now()
    start = end - timedelta(days=7)
    fs.materialize(start_date=start, end_date=end)
    print("materialized week of features to redis")


if __name__ == "__main__":
    main()
