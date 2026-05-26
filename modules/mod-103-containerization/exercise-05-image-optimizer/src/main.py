"""
Container Image Optimizer - CLI Entry Point

Analyze a Dockerfile for optimization opportunities, or rewrite it
with automated transformations.

Subcommands:
    analyze     Surface findings without modifying the Dockerfile.
    optimize    Produce an optimized Dockerfile (writes new file or stdout).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .analyzer import DockerfileAnalyzer, DockerfileParser, FindingSeverity
from .optimizer import DockerfileOptimizer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Docker image optimizer."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.argument("dockerfile", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", default="text", type=click.Choice(["text", "json"]))
@click.option("--min-severity", default="info", type=click.Choice([s.value for s in FindingSeverity]))
def analyze(dockerfile: str, fmt: str, min_severity: str) -> None:
    """Surface findings without modifying the file."""
    parser = DockerfileParser()
    df = parser.parse_file(Path(dockerfile))
    analyzer = DockerfileAnalyzer()
    findings = analyzer.analyze(df)

    severity_order = {s.value: idx for idx, s in enumerate(FindingSeverity)}
    threshold = severity_order[min_severity]
    findings = [f for f in findings if severity_order[f.severity.value] >= threshold]

    if fmt == "json":
        click.echo(json.dumps([_finding_to_dict(f) for f in findings], indent=2))
    else:
        click.echo(f"Dockerfile: {dockerfile}")
        click.echo(f"Stages: {len(df.stages)} ({'multi-stage' if df.is_multi_stage else 'single-stage'})")
        click.echo(f"Findings: {len(findings)}")
        for f in findings:
            click.echo(
                f"  [{f.severity.value.upper()}] {f.rule_id}: {f.title}"
                + (f"  (~{f.estimated_savings_mb:.0f}MB)" if f.estimated_savings_mb else "")
            )
            click.echo(f"    {f.recommendation}")
    sys.exit(2 if any(f.severity in {FindingSeverity.HIGH, FindingSeverity.MEDIUM} for f in findings) else 0)


@cli.command()
@click.argument("dockerfile", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(dir_okay=False),
              help="Write to FILE; defaults to stdout")
def optimize(dockerfile: str, output: Optional[str]) -> None:
    """Generate an optimized Dockerfile."""
    parser = DockerfileParser()
    df = parser.parse_file(Path(dockerfile))
    optimizer = DockerfileOptimizer()
    result = optimizer.optimize(df)
    if output:
        Path(output).write_text(result.optimized_text)
        click.echo(f"Wrote {output}")
    else:
        click.echo(result.optimized_text)
    click.echo("--- transformations applied ---", err=True)
    for t in result.transformations:
        click.echo(f"  • {t}", err=True)
    click.echo(
        f"Findings: {len(result.findings_before)} → {len(result.findings_after)}",
        err=True,
    )
    if result.estimated_savings_mb:
        click.echo(f"Estimated savings: ~{result.estimated_savings_mb:.0f} MB", err=True)


def _finding_to_dict(f) -> dict:
    return {
        "rule_id": f.rule_id,
        "title": f.title,
        "severity": f.severity.value,
        "line_number": f.line_number,
        "stage_index": f.stage_index,
        "description": f.description,
        "recommendation": f.recommendation,
        "estimated_savings_mb": f.estimated_savings_mb,
    }


if __name__ == "__main__":
    cli()
