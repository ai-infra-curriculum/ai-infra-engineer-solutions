"""Compare Infracost output against budget. Exit 1 if over threshold."""
from __future__ import annotations

import argparse
import json
import sys

import yaml


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--infracost", required=True, help="Infracost JSON output")
    p.add_argument("--budgets", required=True)
    p.add_argument("--team", required=True)
    p.add_argument("--current-spend", type=float, default=0, help="Current month spend USD")
    args = p.parse_args()

    budgets = yaml.safe_load(open(args.budgets))["budgets"]
    team_budget = budgets[args.team]
    monthly_budget = team_budget["monthly_usd"]
    block_pct = team_budget["pr_block_threshold_pct"]

    cost_data = json.load(open(args.infracost))
    delta_usd = cost_data.get("diffTotalMonthlyCost", 0)
    projected = args.current_spend + delta_usd

    print(f"Team: {args.team}")
    print(f"Monthly budget: ${monthly_budget}")
    print(f"Current spend: ${args.current_spend:.2f}")
    print(f"PR delta: ${delta_usd:+.2f}")
    print(f"Projected total: ${projected:.2f} ({projected/monthly_budget*100:.1f}% of budget)")

    if projected > monthly_budget * (block_pct / 100):
        print(f"❌ BLOCKED: projected ${projected:.2f} > {block_pct}% of ${monthly_budget}")
        sys.exit(1)
    if projected > monthly_budget * (team_budget["warning_threshold_pct"] / 100):
        print(f"⚠ WARN: projected over warning threshold")
    print("✓ OK")


if __name__ == "__main__":
    main()
