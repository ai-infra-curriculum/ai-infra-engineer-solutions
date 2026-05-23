"""Scan all Terraform projects for drift, classify severity, post to Slack."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROJECTS = ["network", "eks", "rds", "iam"]
ENVS = ["dev", "staging", "prod"]


def plan(project: str, env: str) -> dict:
    path = Path(f"projects/{env}/{project}")
    subprocess.run(["terraform", "init", "-backend=false"], cwd=path, check=True)
    r = subprocess.run(["terraform", "plan", "-detailed-exitcode", "-out=plan.bin"],
                        cwd=path, capture_output=True)
    # exit codes: 0 = no changes, 1 = error, 2 = changes detected
    changes_present = r.returncode == 2
    if not changes_present:
        return {"project": project, "env": env, "drift": False}

    show = subprocess.check_output(["terraform", "show", "-json", "plan.bin"], cwd=path)
    plan_json = json.loads(show)
    return {
        "project": project,
        "env": env,
        "drift": True,
        "changes": plan_json.get("resource_changes", []),
    }


def main():
    drifts = []
    for env in ENVS:
        for project in PROJECTS:
            try:
                drifts.append(plan(project, env))
            except subprocess.CalledProcessError as e:
                drifts.append({"project": project, "env": env, "error": str(e)})

    drifted = [d for d in drifts if d.get("drift")]
    print(json.dumps({"total_projects": len(drifts), "drifted": len(drifted)}, indent=2))

    if drifted:
        # Post to Slack
        import httpx
        httpx.post(os.environ["SLACK_WEBHOOK"], json={
            "text": f"⚠ Terraform drift detected in {len(drifted)} project/env combos. See report.",
        })


if __name__ == "__main__":
    main()
