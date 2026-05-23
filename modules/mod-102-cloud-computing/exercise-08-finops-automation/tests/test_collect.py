"""Unit tests for the report formatter; doesn't hit AWS."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import report  # noqa: E402


def test_weekly_report_sums_correctly(tmp_path):
    df = pd.DataFrame([
        {"date": "2026-05-19", "team": "ml-platform", "service": "EC2", "cost_usd": 100.0},
        {"date": "2026-05-19", "team": "ml-platform", "service": "S3",  "cost_usd": 50.0},
        {"date": "2026-05-20", "team": "recs",        "service": "EC2", "cost_usd": 75.0},
    ])
    budgets = tmp_path / "b.yaml"
    budgets.write_text("ml-platform: 1000\nrecs: 1000\n")
    r = report.weekly_report(df, str(budgets))
    assert r["total_spend"] == 225.0
    teams = {t["team"]: t for t in r["by_team"]}
    assert teams["ml-platform"]["cost_usd"] == 150.0
    assert teams["recs"]["cost_usd"] == 75.0


def test_alert_when_over_budget(tmp_path):
    df = pd.DataFrame([
        {"date": "2026-05-19", "team": "ml-platform", "service": "EC2", "cost_usd": 500.0},
    ])
    budgets = tmp_path / "b.yaml"
    budgets.write_text("ml-platform: 1000\n")    # weekly = 250
    r = report.weekly_report(df, str(budgets))
    assert len(r["alerts"]) == 1


def test_format_markdown_renders(tmp_path):
    df = pd.DataFrame([
        {"date": "2026-05-19", "team": "ml-platform", "service": "EC2", "cost_usd": 100.0},
    ])
    budgets = tmp_path / "b.yaml"
    budgets.write_text("ml-platform: 1000\n")
    r = report.weekly_report(df, str(budgets))
    md = report.format_markdown(r, "2026-05-19")
    assert "ml-platform" in md
    assert "Top services" in md
