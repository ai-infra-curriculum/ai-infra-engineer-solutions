"""Cross-provider latency + throughput benchmarks."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def bench_provider(invoke_fn, n_warm: int = 5, n_measure: int = 100,
                    concurrency: int = 1, payload: dict | None = None) -> dict:
    payload = payload or {"features": [5.1, 3.5, 1.4, 0.2]}

    # warmup
    for _ in range(n_warm):
        invoke_fn(payload)

    # measure
    latencies = []
    if concurrency == 1:
        for _ in range(n_measure):
            t0 = time.perf_counter()
            invoke_fn(payload)
            latencies.append((time.perf_counter() - t0) * 1000)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            t0 = time.perf_counter()
            futures = [ex.submit(invoke_fn, payload) for _ in range(n_measure)]
            for f in as_completed(futures):
                f.result()
            total = time.perf_counter() - t0
        return {"throughput_rps": n_measure / total}

    latencies.sort()
    return {
        "p50_ms": latencies[len(latencies) // 2],
        "p95_ms": latencies[int(len(latencies) * 0.95)],
        "p99_ms": latencies[int(len(latencies) * 0.99)],
    }


def invoke_sagemaker(endpoint_name: str):
    import boto3
    runtime = boto3.client("sagemaker-runtime")

    def _invoke(payload):
        runtime.invoke_endpoint(
            EndpointName=endpoint_name, ContentType="application/json",
            Body=json.dumps(payload).encode(),
        )

    return _invoke


def invoke_vertex(endpoint_id: str, project: str, location: str):
    from google.cloud import aiplatform
    aiplatform.init(project=project, location=location)
    endpoint = aiplatform.Endpoint(endpoint_id)

    def _invoke(payload):
        endpoint.predict(instances=[payload["features"]])

    return _invoke


def invoke_azure(endpoint_name: str, workspace: str, resource_group: str, subscription: str):
    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential
    ml = MLClient(DefaultAzureCredential(), subscription, resource_group, workspace)

    def _invoke(payload):
        ml.online_endpoints.invoke(endpoint_name=endpoint_name, request_file=None,
                                     deployment_name="primary", request_body=json.dumps(payload))

    return _invoke


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", required=True, choices=["sagemaker", "vertex", "azure"])
    p.add_argument("--endpoint", required=True)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--n-measure", type=int, default=100)
    # provider-specific:
    p.add_argument("--gcp-project"); p.add_argument("--gcp-location", default="us-central1")
    p.add_argument("--az-workspace"); p.add_argument("--az-rg"); p.add_argument("--az-sub")
    args = p.parse_args()

    if args.provider == "sagemaker":
        fn = invoke_sagemaker(args.endpoint)
    elif args.provider == "vertex":
        fn = invoke_vertex(args.endpoint, args.gcp_project, args.gcp_location)
    else:
        fn = invoke_azure(args.endpoint, args.az_workspace, args.az_rg, args.az_sub)

    result = bench_provider(fn, n_measure=args.n_measure, concurrency=args.concurrency)
    print(json.dumps({"provider": args.provider, **result}, indent=2))


if __name__ == "__main__":
    main()
