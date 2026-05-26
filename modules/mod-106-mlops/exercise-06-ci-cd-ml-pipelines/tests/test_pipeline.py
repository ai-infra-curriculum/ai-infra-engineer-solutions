"""Tests for the CI/CD pipeline runner + validators."""

from typing import Dict, List

import pytest

from src.pipeline import (
    BlueGreenState,
    BuildReport,
    DeployReport,
    MLPipeline,
    PipelineConfig,
    PipelineContext,
    StageStatus,
    TestReport,
    TrainReport,
    make_demo_steps,
)
from src.validators import (
    JobDefinition,
    Severity,
    WorkflowDefinition,
    validate_dockerfile,
    validate_requirements,
    validate_workflow,
)


def _approval_yes(_ctx) -> bool:
    return True


def _build_pipeline(
    *,
    config: PipelineConfig = None,
    accuracy: float = 0.92,
    image_size_mb: float = 850.0,
    smoke_tests_passed: bool = True,
    rolled_back: List[str] = None,
) -> MLPipeline:
    rolled_back = rolled_back if rolled_back is not None else []
    steps = make_demo_steps(
        accuracy=accuracy,
        image_size_mb=image_size_mb,
        smoke_tests_passed=smoke_tests_passed,
    )
    return MLPipeline(
        config=config or PipelineConfig(),
        test_fn=steps["test"], train_fn=steps["train"], build_fn=steps["build"],
        staging_deploy_fn=steps["staging"], production_deploy_fn=steps["production"],
        production_approval_fn=_approval_yes,
        rollback_fn=lambda ctx, stage: rolled_back.append(stage),
    )


class TestPipelineRun:
    def test_happy_path(self):
        pipeline = _build_pipeline()
        run = pipeline.run(commit_sha="abc", branch="main")
        assert run.passed
        for stage in run.stages:
            assert stage.status in {StageStatus.SUCCESS, StageStatus.SKIPPED}
        assert run.final_environment == "production"

    def test_test_stage_failure_skips_downstream(self):
        # Force low coverage to fail tests.
        config = PipelineConfig(min_test_coverage_percent=99.9)
        pipeline = _build_pipeline(config=config)
        run = pipeline.run(commit_sha="abc", branch="main")
        statuses = {s.name: s.status for s in run.stages}
        assert statuses["test"] is StageStatus.FAILED
        # The train stage may not be appended at all when test fails;
        # check that no successful downstream stages exist.
        assert "train" not in {s.name for s in run.stages if s.status is StageStatus.SUCCESS}

    def test_train_failure_rejects_below_threshold(self):
        config = PipelineConfig(required_model_metrics={"accuracy": 0.95})
        pipeline = _build_pipeline(config=config, accuracy=0.80)
        run = pipeline.run(commit_sha="abc", branch="main")
        assert not run.passed
        train_stage = run.stage("train")
        assert train_stage.status is StageStatus.FAILED
        assert "accuracy=0.8000" in train_stage.error

    def test_build_failure_on_image_size(self):
        config = PipelineConfig(max_image_size_mb=500.0)
        pipeline = _build_pipeline(config=config, image_size_mb=2000.0)
        run = pipeline.run(commit_sha="abc", branch="main")
        assert not run.passed
        assert run.stage("build").status is StageStatus.FAILED

    def test_production_smoke_failure_rolls_back(self):
        rolled_back: List[str] = []
        pipeline = _build_pipeline(smoke_tests_passed=False, rolled_back=rolled_back)
        run = pipeline.run(commit_sha="abc", branch="main")
        assert run.rolled_back
        assert "deploy_production" in rolled_back
        assert run.stage("deploy_production").status is StageStatus.ROLLED_BACK

    def test_production_requires_approval(self):
        config = PipelineConfig(require_production_approval=True)
        steps = make_demo_steps()
        denied_approval = lambda ctx: False
        pipeline = MLPipeline(
            config=config,
            test_fn=steps["test"], train_fn=steps["train"], build_fn=steps["build"],
            staging_deploy_fn=steps["staging"], production_deploy_fn=steps["production"],
            production_approval_fn=denied_approval,
        )
        run = pipeline.run(commit_sha="abc", branch="main")
        assert run.stage("deploy_production").status is StageStatus.SKIPPED
        # Pipeline still passes overall — production deploy was skipped, not failed.
        assert run.passed
        # Final environment should reflect the most recent successful deploy.
        assert run.final_environment == "staging"

    def test_no_approval_required_when_disabled(self):
        config = PipelineConfig(require_production_approval=False)
        pipeline = _build_pipeline(config=config)
        run = pipeline.run(commit_sha="abc", branch="main")
        assert run.stage("deploy_production").status is StageStatus.SUCCESS


class TestBlueGreen:
    def test_swap_changes_live_color(self):
        state = BlueGreenState(environment="prod")
        assert state.live_color == "blue"
        new_color = state.swap(reason="cutover")
        assert new_color == "green"
        assert state.live_color == "green"
        assert state.pending_color == "blue"

    def test_history_records_swaps(self):
        state = BlueGreenState(environment="prod")
        state.swap(reason="initial cutover")
        state.swap(reason="rollback after bug")
        assert len(state.history) == 2
        assert state.history[0]["new_live_color"] == "green"
        assert state.history[1]["new_live_color"] == "blue"


class TestWorkflowValidator:
    def _wf(self, **overrides) -> WorkflowDefinition:
        return WorkflowDefinition(
            name=overrides.get("name", "ml-ci"),
            on=overrides.get("on", ["push", "pull_request"]),
            jobs=overrides.get("jobs", {
                "test": JobDefinition(name="test", runs_on="ubuntu-latest",
                                       steps=[{"run": "pytest"}]),
                "train": JobDefinition(name="train", runs_on="ubuntu-latest",
                                       steps=[{"run": "python train.py"}], needs=["test"]),
                "build": JobDefinition(name="build", runs_on="ubuntu-latest",
                                       steps=[{"run": "docker build"}], needs=["train"]),
                "deploy_staging": JobDefinition(
                    name="deploy_staging", runs_on="ubuntu-latest",
                    steps=[{"run": "kubectl apply"}], needs=["build"]),
            }),
        )

    def test_passes_complete_workflow(self):
        report = validate_workflow(self._wf())
        assert report.passed

    def test_missing_required_job_fails(self):
        wf = self._wf(jobs={"test": JobDefinition(name="test", runs_on="ubuntu-latest",
                                                  steps=[{"run": "pytest"}])})
        report = validate_workflow(wf)
        assert not report.passed
        assert any(f.rule_id == "missing_required_jobs" for f in report.findings)

    def test_unknown_dependency_fails(self):
        wf = self._wf(jobs={
            "test": JobDefinition(name="test", runs_on="ubuntu-latest",
                                  steps=[{"run": "pytest"}]),
            "train": JobDefinition(name="train", runs_on="ubuntu-latest",
                                   steps=[{"run": "x"}], needs=["nope"]),
            "build": JobDefinition(name="build", runs_on="ubuntu-latest",
                                   steps=[{"run": "x"}], needs=["train"]),
            "deploy_staging": JobDefinition(name="deploy_staging", runs_on="ubuntu-latest",
                                            steps=[{"run": "x"}], needs=["build"]),
        })
        report = validate_workflow(wf)
        assert any(f.rule_id == "unknown_dependency" for f in report.findings)

    def test_unsupported_runner_warns(self):
        wf = self._wf(jobs={
            "test": JobDefinition(name="test", runs_on="my-self-hosted",
                                  steps=[{"run": "pytest"}]),
            "train": JobDefinition(name="train", runs_on="ubuntu-latest",
                                   steps=[{"run": "x"}], needs=["test"]),
            "build": JobDefinition(name="build", runs_on="ubuntu-latest",
                                   steps=[{"run": "x"}], needs=["train"]),
            "deploy_staging": JobDefinition(name="deploy_staging", runs_on="ubuntu-latest",
                                            steps=[{"run": "x"}], needs=["build"]),
        })
        report = validate_workflow(wf)
        assert any(f.rule_id == "unsupported_runner" for f in report.findings)
        # Warning only; should still pass.
        assert report.passed


class TestRequirementsValidator:
    def test_pinned_requirements_pass(self):
        content = "requests==2.31.0\nnumpy==1.26.3\n# comment\n\n"
        report = validate_requirements(content)
        assert report.passed

    def test_unpinned_fails(self):
        report = validate_requirements("requests>=2.0\n")
        assert not report.passed
        assert any(f.rule_id == "unpinned_requirement" for f in report.findings)

    def test_vulnerable_package_flagged(self):
        report = validate_requirements("urllib3==1.25.0\n")
        assert not report.passed
        assert any(f.rule_id == "vulnerable_dependency" for f in report.findings)

    def test_duplicate_warns(self):
        report = validate_requirements("requests==2.31.0\nrequests==2.31.0\n")
        assert any(f.rule_id == "duplicate_requirement" for f in report.findings)


class TestDockerfileValidator:
    GOOD = (
        "FROM python:3.11.5-slim\n"
        "RUN useradd -m app\n"
        "USER app\n"
        "COPY . .\n"
        "HEALTHCHECK CMD curl -fsS http://localhost:8000/health || exit 1\n"
        "CMD [\"python\", \"app.py\"]\n"
    )
    BAD = (
        "FROM python:latest\n"
        "COPY . .\n"
        "CMD [\"python\", \"app.py\"]\n"
    )

    def test_clean_dockerfile_passes(self):
        report = validate_dockerfile(self.GOOD)
        assert report.passed

    def test_latest_tag_fails(self):
        report = validate_dockerfile(self.BAD)
        assert not report.passed
        assert any(f.rule_id == "unpinned_base_image" for f in report.findings)
        assert any(f.rule_id == "root_user" for f in report.findings)

    def test_missing_healthcheck_warns(self):
        content = (
            "FROM python:3.11.5-slim\n"
            "RUN useradd -m app\n"
            "USER app\n"
            "CMD [\"python\", \"app.py\"]\n"
        )
        report = validate_dockerfile(content)
        # Missing healthcheck is a warning, not an error → passes.
        assert report.passed
        assert any(
            f.rule_id == "missing_healthcheck" and f.severity is Severity.WARNING
            for f in report.findings
        )


class TestVersionComparator:
    def test_ordering(self):
        from src.validators import _version_lt
        assert _version_lt("2.0.0", "2.0.1")
        assert _version_lt("1.9.10", "2.0.0")
        assert not _version_lt("2.0.0", "1.9.10")
        assert not _version_lt("2.0.0", "2.0.0")
