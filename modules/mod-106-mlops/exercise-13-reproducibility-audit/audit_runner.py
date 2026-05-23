"""Drive a reproducibility audit programmatically."""
from __future__ import annotations

import argparse
import json
import subprocess

import mlflow
from mlflow.tracking import MlflowClient


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("version")
    args = p.parse_args()

    client = MlflowClient()
    mv = client.get_model_version(args.name, args.version)
    run = client.get_run(mv.run_id)

    report = {
        "model": args.name,
        "version": args.version,
        "checks": {
            "run_id_present": bool(run.info.run_id),
            "params_logged": bool(run.data.params),
            "metrics_logged": bool(run.data.metrics),
            "git_sha_tagged": "mlflow.source.git.commit" in run.data.tags,
            "seed_param": "seed" in run.data.params or "random_state" in run.data.params,
            "requirements_artifact": False,        # check via list_artifacts
        },
    }

    arts = [a.path for a in client.list_artifacts(run.info.run_id)]
    report["checks"]["requirements_artifact"] = any("requirements" in a for a in arts)
    report["checks"]["model_artifact"] = any(a.endswith(("/", ".pkl", ".joblib", ".onnx"))
                                              for a in arts)

    report["score"] = sum(report["checks"].values()) / len(report["checks"])
    report["verdict"] = (
        "REPRODUCIBLE" if report["score"] >= 0.85
        else "PARTIAL" if report["score"] >= 0.5
        else "NOT_REPRODUCIBLE"
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
