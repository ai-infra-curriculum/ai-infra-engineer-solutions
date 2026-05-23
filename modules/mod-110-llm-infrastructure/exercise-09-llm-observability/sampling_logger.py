"""Log 1% of prompt + completion pairs to S3 for offline analysis."""
import json
import random
import time
from datetime import UTC, datetime

import boto3


SAMPLE_RATE = 0.01
BUCKET = "llm-conversation-samples"


s3 = boto3.client("s3")


def maybe_log(model: str, tenant: str, prompt: str, completion: str, latency_s: float):
    if random.random() > SAMPLE_RATE:
        return
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "model": model,
        "tenant": tenant,
        "prompt": prompt,
        "completion": completion,
        "latency_s": latency_s,
    }
    key = f"{datetime.now(UTC).strftime('%Y/%m/%d/%H')}/{int(time.time() * 1000)}.json"
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(payload).encode())
