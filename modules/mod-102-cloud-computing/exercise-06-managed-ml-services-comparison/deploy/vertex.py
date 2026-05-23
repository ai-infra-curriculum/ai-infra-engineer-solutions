"""Deploy iris model to a Vertex AI Endpoint as a custom container."""
from __future__ import annotations

import argparse

from google.cloud import aiplatform


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--location", default="us-central1")
    p.add_argument("--image-uri", required=True, help="us-central1-docker.pkg.dev/.../iris:latest")
    p.add_argument("--display-name", default="iris-vertex")
    p.add_argument("--machine-type", default="n1-standard-2")
    args = p.parse_args()

    aiplatform.init(project=args.project, location=args.location)
    model = aiplatform.Model.upload(
        display_name=args.display_name,
        serving_container_image_uri=args.image_uri,
        serving_container_predict_route="/predict",
        serving_container_health_route="/health",
        serving_container_ports=[8000],
    )
    endpoint = model.deploy(
        machine_type=args.machine_type,
        min_replica_count=1, max_replica_count=2,
    )
    print(f"Deployed: {endpoint.resource_name}")


if __name__ == "__main__":
    main()
