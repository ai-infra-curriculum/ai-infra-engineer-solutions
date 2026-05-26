"""
Model Monitoring + Drift Detection — CLI

Subcommands:
    demo            Run a synthetic drift + concept-drift scenario and
                    print the resulting MonitorReport + alerts.
    test-feature    Run a single drift test (KS / PSI / chi-square) on
                    paired sample lists provided via --reference and
                    --live (comma-separated floats).
"""

from __future__ import annotations

import json
import logging
import random
import sys
from dataclasses import asdict
from typing import Dict, List

import click

from .alerting import (
    AlertRouter,
    AlertSeverity,
    InMemoryAlertChannel,
    RoutingRule,
    alerts_from_report,
)
from .drift_detector import (
    DriftDetector,
    DriftTest,
    FeatureSpec,
    chi_square_test,
    ks_test,
    psi_test,
)
from .monitor import (
    ModelMonitor,
    PredictionRecord,
    RetrainingPolicy,
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
    """Model monitoring + drift detection."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--samples", default=500, type=int)
@click.option("--drift-magnitude", default=0.5, type=float,
              help="Mean shift to inject into the live distribution")
@click.option("--accuracy-drop", default=0.10, type=float,
              help="Accuracy regression to inject (e.g., 0.10 → 95% → 85%)")
@click.option("--seed", default=42, type=int)
def demo(samples: int, drift_magnitude: float, accuracy_drop: float, seed: int) -> None:
    """Run a synthetic drift scenario end-to-end."""
    rng = random.Random(seed)
    # Reference: zero-mean normal.
    reference_amount = [rng.gauss(0.0, 1.0) for _ in range(samples)]
    reference_age = [rng.gauss(40.0, 10.0) for _ in range(samples)]
    reference_city = [rng.choice(["NYC", "SF", "LA", "CHI"]) for _ in range(samples)]
    reference = {
        "amount_z": reference_amount,
        "age": reference_age,
        "city": reference_city,
    }

    # Live: shift the mean by drift_magnitude.
    live = {
        "amount_z": [rng.gauss(drift_magnitude, 1.0) for _ in range(samples)],
        "age": [rng.gauss(40.0, 10.0) for _ in range(samples)],  # no drift
        "city": [
            rng.choice(["NYC", "SF", "LA", "CHI", "MIA"])  # new city → categorical drift
            for _ in range(samples)
        ],
    }

    feature_specs = [
        FeatureSpec("amount_z", "numeric", DriftTest.KS),
        FeatureSpec("age", "numeric", DriftTest.PSI),
        FeatureSpec("city", "categorical", DriftTest.CHI_SQUARE),
    ]
    monitor = ModelMonitor(
        feature_specs=feature_specs,
        reference_data=reference,
        reference_accuracy=0.95,
        retraining_policy=RetrainingPolicy(min_accuracy_drop_to_retrain=0.05),
    )

    # Feed labeled predictions reflecting accuracy_drop.
    live_accuracy = 0.95 - accuracy_drop
    for i in range(samples):
        label = 1 if rng.random() < 0.3 else 0
        predicted_correct = rng.random() < live_accuracy
        prediction = label if predicted_correct else (1 - label)
        monitor.observe_prediction(PredictionRecord(
            prediction=prediction, label=label, score=rng.random(),
        ))

    report = monitor.evaluate(live)

    click.echo(f"Drift results ({len(report.drift_results)} features):")
    for r in report.drift_results:
        click.echo(
            f"  {r.feature:<12s} {r.test.value:<10s} "
            f"stat={r.statistic:>7.4f} "
            f"severity={r.severity.value:<10s} detected={r.detected}"
        )
    if report.concept_drift:
        cd = report.concept_drift
        click.echo(
            f"\nConcept drift: reference={cd.reference_accuracy:.4f} → "
            f"live={cd.live_accuracy:.4f} (Δ={cd.delta:+.4f}) "
            f"severity={cd.severity.value} detected={cd.detected}"
        )
    click.echo(
        f"\nPerformance: accuracy={report.performance.accuracy:.4f} "
        f"precision={report.performance.precision:.4f} "
        f"recall={report.performance.recall:.4f}"
    )
    click.echo(f"Retraining required: {report.retraining_required} "
               f"(reason={report.retraining_reason.value})")

    # Run alerts through the router.
    slack = InMemoryAlertChannel("slack")
    pagerduty = InMemoryAlertChannel("pagerduty")
    router = AlertRouter([
        RoutingRule(AlertSeverity.WARNING, slack),
        RoutingRule(AlertSeverity.CRITICAL, pagerduty),
    ])
    fired = 0
    for alert in alerts_from_report(report):
        fired += len(router.emit(alert))
    click.echo(f"\nAlerts sent: {fired}")
    for alert in slack.alerts + pagerduty.alerts:
        click.echo(f"  [{alert.severity.value:<8s}] {alert.title}: {alert.body}")


@cli.command()
@click.option("--feature", default="x")
@click.option("--reference", required=True, help="comma-separated reference values")
@click.option("--live", required=True, help="comma-separated live values")
@click.option("--test", "test_name", default="ks", type=click.Choice([t.value for t in DriftTest]))
def test_feature(feature: str, reference: str, live: str, test_name: str) -> None:
    """Run a single drift test on paired sample lists."""
    if test_name == "chi_square":
        ref_values = reference.split(",")
        live_values = live.split(",")
        result = chi_square_test(feature, ref_values, live_values)
    else:
        ref_values = [float(v) for v in reference.split(",") if v.strip()]
        live_values = [float(v) for v in live.split(",") if v.strip()]
        if test_name == "ks":
            result = ks_test(feature, ref_values, live_values)
        else:
            result = psi_test(feature, ref_values, live_values)
    click.echo(json.dumps({
        "feature": result.feature,
        "test": result.test.value,
        "statistic": result.statistic,
        "p_value": result.p_value,
        "threshold": result.threshold,
        "detected": result.detected,
        "severity": result.severity.value,
    }, indent=2))


if __name__ == "__main__":
    cli()
