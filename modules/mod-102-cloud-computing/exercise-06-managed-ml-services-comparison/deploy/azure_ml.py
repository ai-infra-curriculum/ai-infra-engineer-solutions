"""Deploy iris model to an Azure ML Managed Online Endpoint."""
from __future__ import annotations

import argparse

from azure.ai.ml import MLClient
from azure.ai.ml.entities import ManagedOnlineEndpoint, ManagedOnlineDeployment, Model, Environment
from azure.identity import DefaultAzureCredential


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--subscription", required=True)
    p.add_argument("--resource-group", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--endpoint-name", default="iris-azure")
    p.add_argument("--model-path", required=True, help="local path to model.joblib")
    args = p.parse_args()

    ml = MLClient(DefaultAzureCredential(), args.subscription, args.resource_group, args.workspace)

    endpoint = ManagedOnlineEndpoint(name=args.endpoint_name, auth_mode="key")
    ml.online_endpoints.begin_create_or_update(endpoint).result()

    model = ml.models.create_or_update(Model(path=args.model_path, name="iris-sklearn"))
    env = Environment(
        name="sklearn-env",
        image="mcr.microsoft.com/azureml/sklearn-1.2-1:latest",
    )
    deployment = ManagedOnlineDeployment(
        name="primary",
        endpoint_name=args.endpoint_name,
        model=model.id,
        environment=env,
        instance_type="Standard_DS2_v2",
        instance_count=1,
    )
    ml.online_deployments.begin_create_or_update(deployment).result()
    ml.online_endpoints.begin_update(endpoint_name=args.endpoint_name,
                                      traffic={"primary": 100}).result()
    print(f"Deployed: {args.endpoint_name}")


if __name__ == "__main__":
    main()
