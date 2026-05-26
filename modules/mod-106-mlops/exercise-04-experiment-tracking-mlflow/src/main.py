"""
Experiment Tracking + Model Registry — CLI

Subcommands:
    demo            Train 3 synthetic models, track them, register the
                    best one, and demonstrate auto-promotion + rollback.
    list-runs       Show runs for an experiment.
    promote         Try to promote a candidate version using a policy.
"""

from __future__ import annotations

import json
import logging
import random
import sys
from typing import Optional

import click

from .experiment_tracker import ExperimentTracker, Run, RunStatus
from .model_registry import (
    ModelRegistry,
    PromotionPolicy,
    Stage,
    auto_promote,
    compare_versions,
    make_version_from_run,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _train_synthetic_run(
    tracker: ExperimentTracker,
    *,
    experiment: str,
    learning_rate: float,
    epochs: int,
    seed: int,
    user: str = "demo",
) -> Run:
    rng = random.Random(seed)
    params = {"learning_rate": learning_rate, "epochs": epochs, "seed": seed}
    with tracker.auto_log(experiment, params=params, user=user) as run:
        loss = 1.0
        accuracy = 0.5
        for epoch in range(epochs):
            loss = max(0.01, loss * (0.85 + rng.uniform(-0.05, 0.05)))
            accuracy = min(0.99, accuracy + 0.05 + rng.uniform(-0.01, 0.02))
            tracker.log_metric(run, "loss", loss, step=epoch)
            tracker.log_metric(run, "accuracy", accuracy, step=epoch)
        tracker.log_metric(run, "fairness_score", 0.92 + rng.uniform(-0.02, 0.02))
        tracker.log_artifact(run, f"artifacts/{run.run_id}/model.pkl")
    return run


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Experiment tracking + model registry."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
def demo() -> None:
    """End-to-end demo: 3 runs → best → register → auto-promote → rollback."""
    tracker = ExperimentTracker(default_user="demo")
    registry = ModelRegistry()
    experiment = "fraud-classifier"

    # Three runs with varying hyperparameters.
    runs = [
        _train_synthetic_run(tracker, experiment=experiment, learning_rate=lr,
                             epochs=10, seed=seed)
        for seed, lr in [(1, 0.01), (2, 0.005), (3, 0.001)]
    ]

    click.echo("Runs:")
    for r in runs:
        click.echo(
            f"  {r.run_id}: lr={r.params['learning_rate']} "
            f"accuracy={r.latest_metric('accuracy'):.4f} "
            f"loss={r.latest_metric('loss'):.4f}"
        )

    # Promote the best run as model v1 → Production.
    best = tracker.best_run(experiment, "accuracy")
    v1 = make_version_from_run(
        best,
        model_name="fraud-classifier",
        artifact_uri=f"s3://models/fraud-classifier/{best.run_id}/model.pkl",
        registry=registry,
        description="Initial baseline",
    )
    registry.transition("fraud-classifier", v1.version, Stage.PRODUCTION,
                        actor="demo", reason="Initial deploy")
    click.echo(f"\nPromoted v{v1.version} ({v1.run_id}) to Production")

    # Train a challenger; auto-promote on improvement.
    challenger = _train_synthetic_run(tracker, experiment=experiment,
                                      learning_rate=0.003, epochs=12, seed=42)
    v2 = make_version_from_run(
        challenger,
        model_name="fraud-classifier",
        artifact_uri=f"s3://models/fraud-classifier/{challenger.run_id}/model.pkl",
        registry=registry,
        description="Challenger",
    )
    policy = PromotionPolicy(
        metric="accuracy", higher_is_better=True, min_improvement=0.001,
        forbid_regression_in=["fairness_score"],
    )
    decision = auto_promote(registry, v2, policy, actor="ci")
    click.echo(
        f"Promotion decision for v{v2.version}: "
        f"{'PROMOTED' if decision.promote else 'REJECTED'} — {decision.reason}"
    )

    # Roll back.
    if decision.promote:
        rolled = registry.rollback("fraud-classifier", actor="demo")
        click.echo(f"Rolled back to v{rolled.version}")

    # Final lineage of v2.
    click.echo("\nLineage of v2:")
    click.echo(json.dumps(registry.lineage("fraud-classifier", v2.version), indent=2))


@cli.command()
@click.option("--experiment", required=True)
def list_runs(experiment: str) -> None:
    """List runs for an experiment (only the demo's in-memory backend)."""
    tracker = ExperimentTracker()
    # Re-run the demo data so there's something to list.
    for seed, lr in [(1, 0.01), (2, 0.005)]:
        _train_synthetic_run(tracker, experiment=experiment, learning_rate=lr,
                             epochs=5, seed=seed)
    exp = tracker.backend.get_experiment(experiment)
    if exp is None:
        click.echo(f"No experiment named {experiment!r}")
        return
    runs = tracker.backend.list_runs(exp.experiment_id)
    for r in runs:
        click.echo(
            f"  {r.run_id} status={r.status.value} "
            f"accuracy={r.latest_metric('accuracy'):.4f}"
        )


@cli.command()
@click.option("--metric", default="accuracy")
@click.option("--min-improvement", default=0.001, type=float)
def promote(metric: str, min_improvement: float) -> None:
    """Demonstrate one promotion attempt against a synthetic incumbent."""
    registry = ModelRegistry()
    incumbent = registry.register(
        model_name="m", artifact_uri="s3://incumbent", run_id="r-old",
        metrics={metric: 0.85, "fairness_score": 0.9},
    )
    registry.transition("m", 1, Stage.PRODUCTION, actor="demo", reason="seed")
    candidate = registry.register(
        model_name="m", artifact_uri="s3://candidate", run_id="r-new",
        metrics={metric: 0.87, "fairness_score": 0.92},
    )
    policy = PromotionPolicy(
        metric=metric, min_improvement=min_improvement,
        forbid_regression_in=["fairness_score"],
    )
    decision = auto_promote(registry, candidate, policy)
    click.echo(json.dumps({
        "promoted": decision.promote,
        "reason": decision.reason,
        "deltas": decision.metric_deltas,
        "incumbent_version": incumbent.version,
        "candidate_version": candidate.version,
    }, indent=2))


if __name__ == "__main__":
    cli()
