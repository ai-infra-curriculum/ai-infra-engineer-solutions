"""mlfinops CLI."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

import click
import pandas as pd

from . import collect, idle, report, slack


@click.group()
def cli() -> None:
    """ML FinOps tooling."""


@cli.command(name="collect")
@click.option("--date", "target_date", default=None, help="YYYY-MM-DD")
@click.option("--bucket", default=None, help="S3 bucket for daily parquet")
def collect_cmd(target_date: str | None, bucket: str | None) -> None:
    target = date.fromisoformat(target_date) if target_date else date.today() - timedelta(days=1)
    df = collect.collect_daily(target)
    click.echo(f"collected {len(df)} rows for {target}")
    if bucket:
        path = collect.upload_to_s3(df, bucket, target)
        click.echo(f"uploaded to {path}")


@cli.command(name="idle")
@click.option("--days", default=7)
@click.option("--cpu-threshold", default=5.0)
def idle_cmd(days: int, cpu_threshold: float) -> None:
    ec2_idle = idle.find_idle_ec2(days=days, cpu_threshold=cpu_threshold)
    ebs_unattached = idle.find_unattached_ebs()
    stopped = idle.find_stopped_ec2_over_days(days=30)
    click.echo(json.dumps({
        "idle_ec2": ec2_idle,
        "unattached_ebs": ebs_unattached,
        "stopped_ec2_over_30d": stopped,
    }, indent=2))


@cli.command(name="report")
@click.option("--week", required=True, help="Week-start YYYY-MM-DD (Monday)")
@click.option("--bucket", required=True)
@click.option("--budgets", default="budgets.yaml")
def report_cmd(week: str, bucket: str, budgets: str) -> None:
    week_start = date.fromisoformat(week)
    dfs = []
    for i in range(7):
        d = (week_start + timedelta(days=i)).isoformat()
        import io, boto3
        s3 = boto3.client("s3")
        try:
            obj = s3.get_object(Bucket=bucket, Key=f"daily/{d}.parquet")
            dfs.append(pd.read_parquet(io.BytesIO(obj["Body"].read())))
        except Exception:
            click.echo(f"missing daily: {d}", err=True)

    if not dfs:
        click.echo("no data for week", err=True)
        raise SystemExit(1)

    weekly = pd.concat(dfs, ignore_index=True)
    r = report.weekly_report(weekly, budgets)
    md = report.format_markdown(r, week)
    click.echo(md)


@cli.command(name="digest")
@click.option("--week", required=True)
@click.option("--bucket", required=True)
@click.option("--budgets", default="budgets.yaml")
@click.option("--webhook", default=lambda: os.environ.get("SLACK_WEBHOOK_URL"))
def digest_cmd(week: str, bucket: str, budgets: str, webhook: str | None) -> None:
    if not webhook:
        raise click.UsageError("Set SLACK_WEBHOOK_URL or pass --webhook")

    ctx = click.get_current_context()
    md = ctx.invoke(report_cmd, week=week, bucket=bucket, budgets=budgets)
    # report_cmd echoes; recapture via report module directly
    week_start = date.fromisoformat(week)
    dfs = []
    for i in range(7):
        d = (week_start + timedelta(days=i)).isoformat()
        import io, boto3
        s3 = boto3.client("s3")
        try:
            obj = s3.get_object(Bucket=bucket, Key=f"daily/{d}.parquet")
            dfs.append(pd.read_parquet(io.BytesIO(obj["Body"].read())))
        except Exception:
            pass
    weekly = pd.concat(dfs, ignore_index=True)
    r = report.weekly_report(weekly, budgets)
    slack.post(webhook, report.format_markdown(r, week))
    click.echo("posted to slack")


if __name__ == "__main__":
    cli()
