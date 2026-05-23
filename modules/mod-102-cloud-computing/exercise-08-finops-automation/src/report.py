"""Aggregate per-week per-team report; compare against budgets."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import yaml


def weekly_report(weekly_data: pd.DataFrame, budgets_path: str) -> dict:
    budgets = yaml.safe_load(open(budgets_path))

    summary = weekly_data.groupby("team")["cost_usd"].sum().reset_index()
    summary["budget_monthly"] = summary["team"].map(budgets).fillna(0)
    # weekly = 25% of monthly budget
    summary["budget_weekly"] = summary["budget_monthly"] / 4
    summary["over_budget"] = summary["cost_usd"] > summary["budget_weekly"]

    by_service = weekly_data.groupby("service")["cost_usd"].sum().sort_values(ascending=False).head(5)

    return {
        "total_spend": float(weekly_data["cost_usd"].sum()),
        "by_team": summary.to_dict("records"),
        "top_services": by_service.to_dict(),
        "alerts": summary[summary["over_budget"]].to_dict("records"),
    }


def format_markdown(report: dict, week_label: str) -> str:
    lines = [f"# Weekly FinOps — Week of {week_label}",
             f"\n**Total spend:** ${report['total_spend']:,.2f}\n"]

    lines.append("## Per-team\n")
    lines.append("| Team | Spend | Weekly Budget | Status |")
    lines.append("|---|---|---|---|")
    for t in report["by_team"]:
        status = "🚨 OVER" if t["over_budget"] else "✅"
        lines.append(f"| {t['team']} | ${t['cost_usd']:,.2f} | ${t['budget_weekly']:,.2f} | {status} |")

    lines.append("\n## Top services\n")
    lines.append("| Service | Cost |")
    lines.append("|---|---|")
    for service, cost in report["top_services"].items():
        lines.append(f"| {service} | ${cost:,.2f} |")

    if report["alerts"]:
        lines.append("\n## ⚠️ Over-budget teams\n")
        for a in report["alerts"]:
            lines.append(f"- **{a['team']}** spent ${a['cost_usd']:,.2f} (budget ${a['budget_weekly']:,.2f})")

    return "\n".join(lines)
