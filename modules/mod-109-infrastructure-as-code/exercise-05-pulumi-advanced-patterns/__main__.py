"""Pulumi entrypoint: ComponentResource + dynamic loops + cross-stack."""
import pulumi
import yaml
from pulumi import StackReference

from components.ml_namespace import MlNamespace


# Cross-stack reference: read VPC outputs from another stack
network = StackReference(f"{pulumi.get_organization()}/network/{pulumi.get_stack()}")
vpc_id = network.get_output("vpc_id")

# Dynamic resource generation: one namespace per team from YAML config
teams = yaml.safe_load(open("teams.yaml"))["teams"]
for t in teams:
    MlNamespace(
        f"team-{t['name']}",
        team=t["name"],
        owner_emails=t["owners"],
        gpu_quota=t.get("gpu_quota", 0),
    )

pulumi.export("vpc_id", vpc_id)
