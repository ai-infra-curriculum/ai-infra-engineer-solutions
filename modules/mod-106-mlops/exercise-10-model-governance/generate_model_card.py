"""Auto-fill model card template from MLflow run metadata."""
import argparse

import mlflow
from mlflow.tracking import MlflowClient


TEMPLATE = open("MODEL_CARD_TEMPLATE.md").read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("version")
    args = p.parse_args()

    client = MlflowClient()
    mv = client.get_model_version(args.name, args.version)
    run = client.get_run(mv.run_id)

    filled = (TEMPLATE
              .replace("{MODEL_NAME}", args.name)
              .replace("{VERSION}", args.version)
              .replace("{ALGO}", run.data.tags.get("estimator_name", "unknown"))
              .replace("{HYPERPARAMS}", str(run.data.params))
              .replace("{METRIC}", "accuracy")
              .replace("{VALUE}", str(run.data.metrics.get("accuracy_score", "")))
              .replace("{DATE}", mv.creation_timestamp.__str__()))
    print(filled)


if __name__ == "__main__":
    main()
