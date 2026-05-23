"""Monthly cost computation from workloads + price table."""
from __future__ import annotations

import argparse

import yaml


HOURS_PER_MONTH = 24 * 30


def monthly_cost(workload: dict, prices: dict) -> float:
    gpu = workload["gpu"]
    price_per_hr = prices[gpu][workload["purchase"]]
    instances = workload["avg_instances"]

    hpd = workload.get("hours_per_day")
    if hpd is not None:
        days_per_week = workload.get("days_per_week", 7)
        hours_per_month = hpd * days_per_week * (30 / 7)
    else:
        hpw = workload.get("hours_per_week", 0)
        hours_per_month = hpw * (30 / 7)

    return instances * price_per_hr * hours_per_month


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workloads", default="workloads.yaml")
    p.add_argument("--prices", default="prices.yaml")
    args = p.parse_args()

    prices = yaml.safe_load(open(args.prices))
    workloads = yaml.safe_load(open(args.workloads))

    total = 0.0
    naive_baseline = 0.0   # what we'd pay if all workloads went on H100 on-demand 24/7

    print(f"{'workload':<30} {'gpu':<10} {'purchase':<14} {'monthly':>12}")
    for w in workloads:
        cost = monthly_cost(w, prices)
        total += cost

        # naive: same compute on H100 on-demand 24/7
        h100_naive = w["avg_instances"] * prices["H100"]["on_demand"] * HOURS_PER_MONTH
        naive_baseline += h100_naive

        print(f"{w['name']:<30} {w['gpu']:<10} {w['purchase']:<14} ${cost:>10.0f}")

    print(f"{'TOTAL':<55} ${total:>10.0f}")
    print(f"{'Naive baseline (all on H100 on-demand)':<55} ${naive_baseline:>10.0f}")
    print(f"Savings: {(1 - total / naive_baseline) * 100:.0f}%")


if __name__ == "__main__":
    main()
