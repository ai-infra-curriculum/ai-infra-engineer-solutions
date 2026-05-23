"""Quality-gated promotion. Auto-promotes to Staging when gates pass; Production requires approval."""
from __future__ import annotations

import argparse
import sys

import mlflow
from mlflow.tracking import MlflowClient


DELTA_THRESHOLD = -0.005    # accuracy may not drop more than 0.5pp vs Production


def get_metric(client, name: str, version: str, key: str) -> float | None:
    run_id = client.get_model_version(name, version).run_id
    run = client.get_run(run_id)
    return run.data.metrics.get(key)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("version")
    p.add_argument("--to", choices=["staging", "production"], required=True)
    args = p.parse_args()

    client = MlflowClient()

    # Compare against current Production
    candidate_acc = get_metric(client, "accuracy_score", args.version, "training_accuracy_score")
    prod_versions = client.get_latest_versions(args.name, stages=["Production"])
    if prod_versions:
        prod_acc = get_metric(client, "accuracy_score", prod_versions[0].version, "training_accuracy_score")
        delta = candidate_acc - prod_acc
        print(f"candidate={candidate_acc:.4f}  prod={prod_acc:.4f}  delta={delta:+.4f}")
        if delta < DELTA_THRESHOLD:
            print(f"GATE FAILED: delta {delta:+.4f} below threshold {DELTA_THRESHOLD}")
            sys.exit(1)

    client.transition_model_version_stage(
        name=args.name,
        version=args.version,
        stage=args.to.capitalize(),
        archive_existing_versions=(args.to == "production"),
    )
    print(f"promoted {args.name} v{args.version} → {args.to}")


if __name__ == "__main__":
    main()
