"""Per-model training cost from Kubernetes Jobs."""
from __future__ import annotations

import json

from kubernetes import client, config


INSTANCE_HOURLY = {
    "n1-standard-8": 0.38,
    "g4dn.xlarge":   0.526,
    "p3.2xlarge":    3.06,
    "a2-highgpu-1g": 3.67,
}


def main():
    config.load_kube_config()
    batch = client.BatchV1Api()
    jobs = batch.list_job_for_all_namespaces(label_selector="model_name").items

    cost_per_model: dict[str, float] = {}
    for j in jobs:
        model = j.metadata.labels["model_name"]
        instance = j.metadata.labels.get("instance_type", "n1-standard-8")
        if not j.status.start_time or not j.status.completion_time:
            continue
        duration_h = (j.status.completion_time - j.status.start_time).total_seconds() / 3600
        cost = duration_h * INSTANCE_HOURLY.get(instance, 0.5)
        cost_per_model[model] = cost_per_model.get(model, 0.0) + cost

    print(json.dumps(cost_per_model, indent=2))


if __name__ == "__main__":
    main()
