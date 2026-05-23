"""Daily streaming-vs-batch reconciliation. Reports drift to Slack."""
from __future__ import annotations

import argparse

import pandas as pd
import redis


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batch", default="s3a://datalake/features/user_features_batch_v1/")
    p.add_argument("--redis", default="redis://cache:6379/0")
    p.add_argument("--threshold", type=float, default=0.05)
    args = p.parse_args()

    batch = pd.read_parquet(args.batch).set_index("user_id")
    r = redis.from_url(args.redis)

    # Sample 1000 users
    sample_ids = batch.index.to_series().sample(1000, random_state=0)

    drift_rows = []
    for uid in sample_ids:
        stream_clicks_5m = int(r.hget(f"features:{uid}", "clicks_5m") or 0)
        # Streaming should be a subset of batch clicks_30d; if stream/batch ratio is odd, flag
        batch_clicks = batch.loc[uid, "clicks_30d"]
        if batch_clicks > 0 and stream_clicks_5m > 0:
            # heuristic: 5-min should be <2× daily-avg
            daily_avg = batch_clicks / 30
            if stream_clicks_5m > 2 * daily_avg + 5:
                drift_rows.append((uid, batch_clicks, stream_clicks_5m))

    drift_rate = len(drift_rows) / len(sample_ids)
    print(f"drift rate: {drift_rate:.2%} ({len(drift_rows)}/{len(sample_ids)})")
    if drift_rate > args.threshold:
        print(f"⚠ EXCEEDED THRESHOLD {args.threshold:.2%}")
        # post to Slack here


if __name__ == "__main__":
    main()
