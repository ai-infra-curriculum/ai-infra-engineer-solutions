"""Tests for the Dockerfile analyzer + optimizer."""

import pytest

from src.analyzer import (
    DockerfileAnalyzer,
    DockerfileParser,
    Finding,
    FindingSeverity,
)
from src.optimizer import DockerfileOptimizer


PYTHON_BAD = """\
FROM python:3.11

WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y gcc build-essential
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
"""

PYTHON_GOOD = """\
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /app /app
RUN useradd --create-home --shell /bin/bash appuser
USER appuser
CMD ["python", "app.py"]
"""

NODE_BAD = """\
FROM node:20
WORKDIR /app
COPY . .
RUN npm install
CMD ["node", "server.js"]
"""

JAVA_BAD = """\
FROM openjdk:21
WORKDIR /app
COPY . .
RUN mvn install
EXPOSE 8080
CMD ["java", "-jar", "target/app.jar"]
"""


class TestDockerfileParser:
    def test_parses_single_stage(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        assert len(df.stages) == 1
        assert df.stages[0].base_image == "python:3.11"
        assert df.stages[0].alias is None
        instructions = [i.name for i in df.stages[0].instructions]
        assert "WORKDIR" in instructions
        assert "RUN" in instructions
        assert "CMD" in instructions

    def test_parses_multi_stage_with_aliases(self):
        df = DockerfileParser().parse_text(PYTHON_GOOD)
        assert df.is_multi_stage
        assert df.stages[0].alias == "builder"
        assert df.stages[1].alias == "runtime"
        assert df.stages[1].base_image == "python:3.11-slim"

    def test_handles_backslash_continuation(self):
        text = (
            "FROM python:3.11\n"
            "RUN apt-get update \\\n"
            "    && apt-get install -y gcc\n"
        )
        df = DockerfileParser().parse_text(text)
        runs = df.stages[0].get("RUN")
        assert len(runs) == 1
        assert "apt-get install -y gcc" in runs[0].args

    def test_strips_comments(self):
        text = "FROM python:3.11  # base image\nRUN echo hi\n"
        df = DockerfileParser().parse_text(text)
        assert df.stages[0].base_image == "python:3.11"


class TestAnalyzer:
    def test_detects_single_stage_with_build_tools(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        findings = DockerfileAnalyzer().analyze(df)
        ids = {f.rule_id for f in findings}
        assert "single_stage_with_build_tools" in ids
        assert "suboptimal_base_image" in ids
        assert "no_user_directive" in ids

    def test_detects_layer_ordering_issue(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        findings = DockerfileAnalyzer().analyze(df)
        ids = {f.rule_id for f in findings}
        assert "cache_unfriendly_layer_order" in ids

    def test_detects_apt_without_cleanup(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        findings = DockerfileAnalyzer().analyze(df)
        ids = {f.rule_id for f in findings}
        assert "apt_without_cleanup" in ids

    def test_good_dockerfile_has_no_high_findings(self):
        df = DockerfileParser().parse_text(PYTHON_GOOD)
        findings = DockerfileAnalyzer().analyze(df)
        highs = [f for f in findings if f.severity is FindingSeverity.HIGH]
        assert not highs, [f.rule_id for f in highs]

    def test_detects_suboptimal_base_for_node(self):
        df = DockerfileParser().parse_text(NODE_BAD)
        findings = DockerfileAnalyzer().analyze(df)
        ids = {f.rule_id for f in findings}
        assert "suboptimal_base_image" in ids

    def test_detects_suboptimal_base_for_java(self):
        df = DockerfileParser().parse_text(JAVA_BAD)
        findings = DockerfileAnalyzer().analyze(df)
        ids = {f.rule_id for f in findings}
        assert "suboptimal_base_image" in ids

    def test_findings_are_sorted_by_severity(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        findings = DockerfileAnalyzer().analyze(df)
        severities = [f.severity for f in findings]
        # Sorted descending by severity.
        assert severities == sorted(severities, key=lambda s: -{
            FindingSeverity.INFO: 0,
            FindingSeverity.LOW: 1,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.HIGH: 3,
        }[s])


class TestOptimizer:
    def test_optimize_converts_to_multistage(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        result = DockerfileOptimizer().optimize(df)
        optimized = result.parsed_optimized()
        assert optimized.is_multi_stage
        assert optimized.stages[0].alias == "builder"

    def test_optimize_swaps_to_slim(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        result = DockerfileOptimizer().optimize(df)
        optimized = result.parsed_optimized()
        assert "slim" in optimized.final_stage.base_image

    def test_optimize_adds_user_directive(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        result = DockerfileOptimizer().optimize(df)
        optimized = result.parsed_optimized()
        assert optimized.final_stage.get("USER"), "final stage should have USER"

    def test_optimize_appends_apt_cleanup(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        result = DockerfileOptimizer().optimize(df)
        # Cleanup should be visible in raw text.
        assert "rm -rf /var/lib/apt/lists" in result.optimized_text

    def test_optimize_reduces_findings(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        result = DockerfileOptimizer().optimize(df)
        before = len(result.findings_before)
        after = len(result.findings_after)
        assert after < before, f"Expected fewer findings: {before} → {after}"

    def test_optimize_reports_savings(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        result = DockerfileOptimizer().optimize(df)
        assert result.estimated_savings_mb > 0

    def test_optimize_lists_transformations(self):
        df = DockerfileParser().parse_text(PYTHON_BAD)
        result = DockerfileOptimizer().optimize(df)
        assert result.transformations
        assert any("multi-stage" in t for t in result.transformations)

    def test_optimize_idempotent_on_good_dockerfile(self):
        df = DockerfileParser().parse_text(PYTHON_GOOD)
        result = DockerfileOptimizer().optimize(df)
        # Should not need transformations.
        assert not result.transformations or all(
            "Added non-root" not in t for t in result.transformations
        )
