"""Deploy iris model to a SageMaker Endpoint."""
from __future__ import annotations

import argparse

from sagemaker.sklearn.model import SKLearnModel


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model-uri", required=True, help="s3://...model.tar.gz")
    p.add_argument("--role-arn", required=True)
    p.add_argument("--endpoint-name", default="iris-sagemaker")
    p.add_argument("--instance-type", default="ml.t2.medium")
    args = p.parse_args()

    model = SKLearnModel(
        model_data=args.model_uri,
        role=args.role_arn,
        entry_point="../src/inference.py",
        framework_version="1.2-1",
    )
    predictor = model.deploy(
        endpoint_name=args.endpoint_name,
        initial_instance_count=1,
        instance_type=args.instance_type,
    )
    print(f"Deployed: {predictor.endpoint_name}")


if __name__ == "__main__":
    main()
