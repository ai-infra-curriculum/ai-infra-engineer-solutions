"""Identify idle resources: EC2 low CPU, EBS volumes unattached, etc."""
from __future__ import annotations

from datetime import datetime, timedelta

import boto3


def find_idle_ec2(days: int = 7, cpu_threshold: float = 5.0) -> list[dict]:
    ec2 = boto3.client("ec2")
    cw = boto3.client("cloudwatch")

    instances = []
    for page in ec2.get_paginator("describe_instances").paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}],
    ):
        for res in page["Reservations"]:
            for inst in res["Instances"]:
                instances.append({"id": inst["InstanceId"], "type": inst["InstanceType"]})

    idle = []
    for inst in instances:
        avg = _avg_cpu(cw, inst["id"], days)
        if avg is not None and avg < cpu_threshold:
            idle.append({**inst, "avg_cpu": avg})
    return idle


def _avg_cpu(cw, instance_id: str, days: int) -> float | None:
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    resp = cw.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start, EndTime=end,
        Period=86400, Statistics=["Average"],
    )
    if not resp["Datapoints"]:
        return None
    return sum(d["Average"] for d in resp["Datapoints"]) / len(resp["Datapoints"])


def find_unattached_ebs() -> list[dict]:
    ec2 = boto3.client("ec2")
    out = []
    for page in ec2.get_paginator("describe_volumes").paginate(
        Filters=[{"Name": "status", "Values": ["available"]}],
    ):
        for vol in page["Volumes"]:
            out.append({
                "id": vol["VolumeId"], "size_gb": vol["Size"],
                "type": vol["VolumeType"], "create_time": vol["CreateTime"].isoformat(),
            })
    return out


def find_stopped_ec2_over_days(days: int = 30) -> list[dict]:
    ec2 = boto3.client("ec2")
    out = []
    cutoff = datetime.utcnow() - timedelta(days=days)
    for page in ec2.get_paginator("describe_instances").paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}],
    ):
        for res in page["Reservations"]:
            for inst in res["Instances"]:
                # Use last-state transition time if available
                transition = inst.get("StateTransitionReason", "")
                if transition and "(" in transition:
                    out.append({
                        "id": inst["InstanceId"],
                        "type": inst["InstanceType"],
                        "stopped_at": transition,
                    })
    return out
