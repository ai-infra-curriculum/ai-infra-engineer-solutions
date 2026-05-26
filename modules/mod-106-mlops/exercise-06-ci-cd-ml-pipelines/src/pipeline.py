"""
CI/CD Pipeline for ML Workflows

A declarative pipeline runner that mirrors the structure of a typical
GitHub Actions workflow for an ML project: test → train → build →
staging-deploy → production-deploy. Each stage produces a StageResult;
the whole pipeline ends in a PipelineRun summary with overall outcome
+ rollback path on failure.

The runner uses dependency-injected callables for the heavy work so
the same code drives unit tests, the demo CLI, and a real
production-like runner that shells out to docker/kubectl.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence


logger = logging.getLogger(__name__)


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


@dataclass
class StageResult:
    """Outcome of a single pipeline stage."""

    name: str
    status: StageStatus
    started_at: datetime
    ended_at: datetime
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()


@dataclass
class PipelineRun:
    """Full pipeline-run summary."""

    run_id: str
    commit_sha: str
    branch: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    stages: List[StageResult] = field(default_factory=list)
    rolled_back: bool = False
    final_environment: Optional[str] = None

    @property
    def passed(self) -> bool:
        return all(
            s.status in {StageStatus.SUCCESS, StageStatus.SKIPPED}
            for s in self.stages
        ) and not self.rolled_back

    @property
    def duration_seconds(self) -> float:
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds()

    def stage(self, name: str) -> Optional[StageResult]:
        for s in self.stages:
            if s.name == name:
                return s
        return None


@dataclass
class TestReport:
    """Output of the test stage."""

    __test__ = False  # not a pytest collection target

    unit_tests_passed: int
    unit_tests_failed: int
    integration_tests_passed: int
    integration_tests_failed: int
    coverage_percent: float


@dataclass
class TrainReport:
    """Output of the train stage."""

    model_name: str
    model_version: str
    metrics: Dict[str, float]
    artifact_uri: str


@dataclass
class BuildReport:
    """Output of the build stage."""

    image_ref: str
    image_size_mb: float
    sbom_uri: Optional[str] = None


@dataclass
class DeployReport:
    """Output of a deploy stage."""

    environment: str
    target_color: str  # "blue" or "green" for blue-green
    rolled_out_replicas: int
    smoke_tests_passed: bool


# -- Pipeline runner ----------------------------------------------------


@dataclass
class PipelineConfig:
    """Configuration knobs for the pipeline runner."""

    min_test_coverage_percent: float = 80.0
    max_unit_test_failures: int = 0
    max_integration_test_failures: int = 0
    required_model_metrics: Dict[str, float] = field(default_factory=lambda: {"accuracy": 0.85})
    max_image_size_mb: float = 1500.0
    require_production_approval: bool = True
    rollback_on_smoke_test_failure: bool = True


PipelineStep = Callable[["PipelineContext"], Dict[str, Any]]


@dataclass
class PipelineContext:
    """Mutable context passed to each stage."""

    run: PipelineRun
    config: PipelineConfig
    artifacts: Dict[str, Any] = field(default_factory=dict)

    def log(self, stage: str, message: str) -> None:
        result = self.run.stage(stage)
        if result is None:
            return
        result.logs.append(message)


class MLPipeline:
    """Executes the test → train → build → staging → production sequence."""

    STAGE_ORDER = ("test", "train", "build", "deploy_staging", "deploy_production")

    def __init__(
        self,
        *,
        config: PipelineConfig,
        test_fn: Callable[[PipelineContext], TestReport],
        train_fn: Callable[[PipelineContext], TrainReport],
        build_fn: Callable[[PipelineContext], BuildReport],
        staging_deploy_fn: Callable[[PipelineContext], DeployReport],
        production_deploy_fn: Callable[[PipelineContext], DeployReport],
        production_approval_fn: Optional[Callable[[PipelineContext], bool]] = None,
        rollback_fn: Optional[Callable[[PipelineContext, str], None]] = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.config = config
        self.test_fn = test_fn
        self.train_fn = train_fn
        self.build_fn = build_fn
        self.staging_deploy_fn = staging_deploy_fn
        self.production_deploy_fn = production_deploy_fn
        self.production_approval_fn = production_approval_fn or (lambda ctx: True)
        self.rollback_fn = rollback_fn
        self.clock = clock

    def run(
        self,
        *,
        commit_sha: str,
        branch: str,
        run_id: Optional[str] = None,
    ) -> PipelineRun:
        run_id = run_id or f"pipeline-{self.clock().strftime('%Y%m%dT%H%M%S')}"
        run = PipelineRun(
            run_id=run_id,
            commit_sha=commit_sha,
            branch=branch,
            started_at=self.clock(),
        )
        ctx = PipelineContext(run=run, config=self.config)

        for stage_name in self.STAGE_ORDER:
            stage_result = StageResult(
                name=stage_name, status=StageStatus.RUNNING,
                started_at=self.clock(), ended_at=self.clock(),
            )
            run.stages.append(stage_result)

            # Decide whether to run or skip this stage.
            should_skip, skip_reason = self._should_skip(stage_name, ctx)
            if should_skip:
                stage_result.status = StageStatus.SKIPPED
                stage_result.ended_at = self.clock()
                stage_result.logs.append(f"Skipped: {skip_reason}")
                continue

            try:
                if stage_name == "test":
                    report = self.test_fn(ctx)
                    self._validate_test_report(report, ctx)
                    ctx.artifacts["test"] = report
                    stage_result.output = _to_dict(report)
                elif stage_name == "train":
                    report = self.train_fn(ctx)
                    self._validate_train_report(report, ctx)
                    ctx.artifacts["train"] = report
                    stage_result.output = _to_dict(report)
                elif stage_name == "build":
                    report = self.build_fn(ctx)
                    self._validate_build_report(report, ctx)
                    ctx.artifacts["build"] = report
                    stage_result.output = _to_dict(report)
                elif stage_name == "deploy_staging":
                    report = self.staging_deploy_fn(ctx)
                    self._validate_deploy(report, ctx, environment="staging")
                    ctx.artifacts["deploy_staging"] = report
                    stage_result.output = _to_dict(report)
                    run.final_environment = "staging"
                elif stage_name == "deploy_production":
                    if self.config.require_production_approval:
                        approved = self.production_approval_fn(ctx)
                        if not approved:
                            stage_result.status = StageStatus.SKIPPED
                            stage_result.logs.append("Production deploy not approved.")
                            stage_result.ended_at = self.clock()
                            continue
                    report = self.production_deploy_fn(ctx)
                    self._validate_deploy(report, ctx, environment="production")
                    ctx.artifacts["deploy_production"] = report
                    stage_result.output = _to_dict(report)
                    run.final_environment = "production"

                stage_result.status = StageStatus.SUCCESS
            except Exception as exc:
                stage_result.status = StageStatus.FAILED
                stage_result.error = f"{type(exc).__name__}: {exc}"
                logger.warning("Stage %s failed: %s", stage_name, exc)
                if (
                    stage_name in {"deploy_staging", "deploy_production"}
                    and self.config.rollback_on_smoke_test_failure
                    and self.rollback_fn is not None
                ):
                    self.rollback_fn(ctx, stage_name)
                    run.rolled_back = True
                    stage_result.status = StageStatus.ROLLED_BACK
                break
            finally:
                stage_result.ended_at = self.clock()

        run.ended_at = self.clock()
        return run

    # -- validation helpers --------------------------------------------

    def _should_skip(self, stage_name: str, ctx: PipelineContext) -> tuple[bool, str]:
        # Skip downstream stages if any prior stage failed.
        prior_failed = any(
            s.status in {StageStatus.FAILED, StageStatus.ROLLED_BACK}
            for s in ctx.run.stages[:-1]
        )
        if prior_failed:
            return True, "Skipped due to upstream failure"
        return False, ""

    def _validate_test_report(self, report: TestReport, ctx: PipelineContext) -> None:
        if report.unit_tests_failed > self.config.max_unit_test_failures:
            raise RuntimeError(
                f"Unit-test failures {report.unit_tests_failed} exceed allowed "
                f"{self.config.max_unit_test_failures}"
            )
        if report.integration_tests_failed > self.config.max_integration_test_failures:
            raise RuntimeError(
                f"Integration-test failures {report.integration_tests_failed} "
                f"exceed allowed {self.config.max_integration_test_failures}"
            )
        if report.coverage_percent < self.config.min_test_coverage_percent:
            raise RuntimeError(
                f"Coverage {report.coverage_percent}% below threshold "
                f"{self.config.min_test_coverage_percent}%"
            )

    def _validate_train_report(self, report: TrainReport, ctx: PipelineContext) -> None:
        for metric, threshold in self.config.required_model_metrics.items():
            observed = report.metrics.get(metric)
            if observed is None:
                raise RuntimeError(f"Train report missing required metric {metric!r}")
            if observed < threshold:
                raise RuntimeError(
                    f"Metric {metric}={observed:.4f} below threshold {threshold:.4f}"
                )

    def _validate_build_report(self, report: BuildReport, ctx: PipelineContext) -> None:
        if report.image_size_mb > self.config.max_image_size_mb:
            raise RuntimeError(
                f"Image size {report.image_size_mb}MB exceeds limit "
                f"{self.config.max_image_size_mb}MB"
            )

    def _validate_deploy(
        self,
        report: DeployReport,
        ctx: PipelineContext,
        *,
        environment: str,
    ) -> None:
        if not report.smoke_tests_passed:
            raise RuntimeError(
                f"Smoke tests failed in {environment} (color={report.target_color})"
            )
        if report.rolled_out_replicas <= 0:
            raise RuntimeError(
                f"No replicas rolled out in {environment}"
            )


def _to_dict(report) -> Dict[str, Any]:
    from dataclasses import asdict, is_dataclass
    if is_dataclass(report):
        return asdict(report)
    return dict(report.__dict__)


# -- Blue/green deploy helpers ------------------------------------------


@dataclass
class BlueGreenState:
    """Tracks which color is currently live for an environment."""

    environment: str
    live_color: str = "blue"  # the current production-serving color
    pending_color: str = "green"  # rolled out but not yet promoted
    history: List[Dict[str, Any]] = field(default_factory=list)

    def swap(self, *, reason: str) -> str:
        self.live_color, self.pending_color = self.pending_color, self.live_color
        self.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_live_color": self.live_color,
            "reason": reason,
        })
        return self.live_color


def make_demo_steps(
    *,
    accuracy: float = 0.92,
    image_size_mb: float = 850.0,
    smoke_tests_passed: bool = True,
) -> Dict[str, Callable[[PipelineContext], Any]]:
    """Build the demo step set used by the CLI."""

    def _test(_ctx: PipelineContext) -> TestReport:
        return TestReport(
            unit_tests_passed=120, unit_tests_failed=0,
            integration_tests_passed=24, integration_tests_failed=0,
            coverage_percent=87.5,
        )

    def _train(_ctx: PipelineContext) -> TrainReport:
        return TrainReport(
            model_name="fraud-classifier",
            model_version="ci-v1",
            metrics={"accuracy": accuracy, "f1": accuracy - 0.05},
            artifact_uri="s3://artifacts/fraud-classifier/ci-v1",
        )

    def _build(_ctx: PipelineContext) -> BuildReport:
        return BuildReport(
            image_ref="registry.example.com/fraud-classifier:ci-v1",
            image_size_mb=image_size_mb,
            sbom_uri="s3://sboms/fraud-classifier-ci-v1.cdx.json",
        )

    def _staging(_ctx: PipelineContext) -> DeployReport:
        return DeployReport(
            environment="staging",
            target_color="green",
            rolled_out_replicas=3,
            smoke_tests_passed=True,
        )

    def _production(_ctx: PipelineContext) -> DeployReport:
        return DeployReport(
            environment="production",
            target_color="green",
            rolled_out_replicas=10,
            smoke_tests_passed=smoke_tests_passed,
        )

    return {
        "test": _test, "train": _train, "build": _build,
        "staging": _staging, "production": _production,
    }
