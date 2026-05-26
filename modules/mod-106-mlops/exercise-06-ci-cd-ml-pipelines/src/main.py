"""
CI/CD for ML Pipelines — CLI

Subcommands:
    run             Run the full test → train → build → deploy pipeline
                    against synthetic stage callables. Prints stage
                    durations + statuses, exits non-zero on failure.
    inject-failure  Force a specific stage to fail and demonstrate the
                    skip + rollback flow.
    validate        Run the workflow / requirements / Dockerfile
                    validators against text input.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .pipeline import (
    MLPipeline,
    PipelineConfig,
    PipelineContext,
    DeployReport,
    make_demo_steps,
)
from .validators import (
    JobDefinition,
    WorkflowDefinition,
    validate_dockerfile,
    validate_requirements,
    validate_workflow,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """CI/CD pipeline for ML projects."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def _build_pipeline(*, accuracy: float = 0.92, image_size_mb: float = 850.0,
                    smoke_tests_passed: bool = True,
                    require_approval: bool = True) -> MLPipeline:
    config = PipelineConfig(require_production_approval=require_approval)
    steps = make_demo_steps(
        accuracy=accuracy,
        image_size_mb=image_size_mb,
        smoke_tests_passed=smoke_tests_passed,
    )
    rolled_back: list[str] = []

    def _approval(_ctx: PipelineContext) -> bool:
        # Auto-approve in demo mode.
        return True

    def _rollback(_ctx: PipelineContext, stage: str) -> None:
        rolled_back.append(stage)
        logger.info("Rolled back stage %s", stage)

    return MLPipeline(
        config=config,
        test_fn=steps["test"], train_fn=steps["train"], build_fn=steps["build"],
        staging_deploy_fn=steps["staging"], production_deploy_fn=steps["production"],
        production_approval_fn=_approval,
        rollback_fn=_rollback,
    )


@cli.command()
@click.option("--commit-sha", default="abc123def456")
@click.option("--branch", default="main")
def run(commit_sha: str, branch: str) -> None:
    """Run the full pipeline."""
    pipeline = _build_pipeline()
    result = pipeline.run(commit_sha=commit_sha, branch=branch)
    _render_run(result)
    if not result.passed:
        sys.exit(2)


@cli.command()
@click.option("--stage", required=True,
              type=click.Choice(["test", "train", "build", "deploy_staging", "deploy_production"]))
def inject_failure(stage: str) -> None:
    """Force one stage to fail and show the cascade behavior."""
    kwargs = {}
    if stage == "test":
        kwargs = dict(accuracy=0.92)  # baseline; force test-stage failure via config
        # Drop min coverage so the test step still produces 87.5% which is below threshold.
        config = PipelineConfig(min_test_coverage_percent=99.9)
        steps = make_demo_steps()
        pipeline = MLPipeline(
            config=config,
            test_fn=steps["test"], train_fn=steps["train"], build_fn=steps["build"],
            staging_deploy_fn=steps["staging"], production_deploy_fn=steps["production"],
            rollback_fn=lambda ctx, stg: None,
        )
    elif stage == "train":
        pipeline = _build_pipeline(accuracy=0.50)  # below 0.85 default
    elif stage == "build":
        pipeline = _build_pipeline(image_size_mb=2000.0)  # above 1500
    elif stage == "deploy_production":
        pipeline = _build_pipeline(smoke_tests_passed=False)
    else:  # deploy_staging
        steps = make_demo_steps()
        def _bad_staging(_ctx: PipelineContext) -> DeployReport:
            return DeployReport(
                environment="staging", target_color="green",
                rolled_out_replicas=3, smoke_tests_passed=False,
            )
        pipeline = MLPipeline(
            config=PipelineConfig(),
            test_fn=steps["test"], train_fn=steps["train"], build_fn=steps["build"],
            staging_deploy_fn=_bad_staging, production_deploy_fn=steps["production"],
            rollback_fn=lambda ctx, stg: None,
        )
    result = pipeline.run(commit_sha="failure-demo", branch="main")
    _render_run(result)


@cli.command()
@click.option("--workflow", type=click.Path(exists=True, dir_okay=False),
              help="JSON workflow definition file")
@click.option("--requirements", type=click.Path(exists=True, dir_okay=False),
              help="Path to requirements.txt")
@click.option("--dockerfile", type=click.Path(exists=True, dir_okay=False))
def validate(workflow: Optional[str], requirements: Optional[str], dockerfile: Optional[str]) -> None:
    """Run validators against supplied artifact paths."""
    if not any([workflow, requirements, dockerfile]):
        raise click.UsageError("Pass at least one of --workflow / --requirements / --dockerfile")

    if workflow:
        body = json.loads(Path(workflow).read_text())
        wf = WorkflowDefinition(
            name=body["name"],
            on=body["on"],
            jobs={
                name: JobDefinition(
                    name=name,
                    runs_on=spec.get("runs_on", "ubuntu-latest"),
                    steps=spec.get("steps", []),
                    needs=spec.get("needs", []),
                )
                for name, spec in body.get("jobs", {}).items()
            },
        )
        _print_report(validate_workflow(wf))

    if requirements:
        _print_report(validate_requirements(Path(requirements).read_text()))

    if dockerfile:
        _print_report(validate_dockerfile(Path(dockerfile).read_text()))


def _render_run(result) -> None:
    click.echo(f"Pipeline {result.run_id}")
    click.echo(f"  branch={result.branch} commit={result.commit_sha[:8]}")
    click.echo(f"  duration={result.duration_seconds:.3f}s")
    click.echo(f"  passed={result.passed}  rolled_back={result.rolled_back}")
    for stage in result.stages:
        marker = {
            "success": "✓", "skipped": "○", "failed": "✗",
            "rolled_back": "↺", "running": "…", "pending": "·",
        }.get(stage.status.value, "?")
        click.echo(
            f"  {marker} {stage.name:<22s} {stage.status.value:<12s} "
            f"duration={stage.duration_seconds:.3f}s "
            + (f"error={stage.error}" if stage.error else "")
        )


def _print_report(report) -> None:
    click.echo(f"\n=== {report.artifact} ===")
    if not report.findings:
        click.echo("  (no findings)")
        return
    for finding in report.findings:
        line_info = f"line {finding.line}: " if finding.line else ""
        click.echo(
            f"  [{finding.severity.value:<7s}] {finding.rule_id}: "
            f"{line_info}{finding.message}"
        )


if __name__ == "__main__":
    cli()
