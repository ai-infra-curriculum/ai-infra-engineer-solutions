"""
Validators for CI/CD ML pipelines

Three classes of pre-flight checks the pipeline runs before letting
code progress through stages:

- WorkflowValidator: lints YAML-style workflow definitions for shape,
  required jobs, and supported actions.
- RequirementsValidator: parses requirements.txt and enforces pinned
  versions + a deny-list of vulnerable packages.
- DockerfileValidator: spot-checks Dockerfiles for production hygiene
  (non-root USER, pinned base image, HEALTHCHECK present).

The validators are intentionally side-effect-free: they accept text
input and return ValidationReport records. The CI pipeline calls them
during the test stage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Set


# -- Validation result types --------------------------------------------


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    message: str
    line: Optional[int] = None


@dataclass
class ValidationReport:
    artifact: str  # what was validated
    findings: List[Finding] = field(default_factory=list)

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def passed(self) -> bool:
        return not self.errors


# -- Workflow validator -------------------------------------------------


# Mandatory job names a complete ML CI workflow should include.
REQUIRED_JOBS = {"test", "train", "build", "deploy_staging"}
ALLOWED_RUNNERS = {"ubuntu-latest", "ubuntu-22.04", "ubuntu-20.04",
                   "macos-latest", "windows-latest"}


@dataclass
class WorkflowDefinition:
    """Subset of a GitHub Actions workflow shape we validate against."""

    name: str
    on: List[str]  # triggers: ["push", "pull_request", ...]
    jobs: Dict[str, "JobDefinition"]


@dataclass
class JobDefinition:
    """One CI job."""

    name: str
    runs_on: str
    steps: List[Dict[str, str]] = field(default_factory=list)
    needs: List[str] = field(default_factory=list)


def validate_workflow(workflow: WorkflowDefinition) -> ValidationReport:
    """Validate the shape + required jobs of a workflow definition."""
    report = ValidationReport(artifact=f"workflow:{workflow.name}")

    if not workflow.name:
        report.findings.append(Finding(
            rule_id="missing_workflow_name", severity=Severity.ERROR,
            message="Workflow must have a non-empty name.",
        ))
    if not workflow.on:
        report.findings.append(Finding(
            rule_id="no_triggers", severity=Severity.ERROR,
            message="Workflow has no triggers (on:).",
        ))

    missing_jobs = REQUIRED_JOBS - set(workflow.jobs.keys())
    if missing_jobs:
        report.findings.append(Finding(
            rule_id="missing_required_jobs", severity=Severity.ERROR,
            message=f"Workflow is missing required jobs: {sorted(missing_jobs)}",
        ))

    for job_name, job in workflow.jobs.items():
        if job.runs_on not in ALLOWED_RUNNERS:
            report.findings.append(Finding(
                rule_id="unsupported_runner", severity=Severity.WARNING,
                message=(
                    f"Job {job_name!r} runs_on {job.runs_on!r}; "
                    f"allowed: {sorted(ALLOWED_RUNNERS)}"
                ),
            ))
        if not job.steps:
            report.findings.append(Finding(
                rule_id="empty_job", severity=Severity.ERROR,
                message=f"Job {job_name!r} has no steps.",
            ))
        for dep in job.needs:
            if dep not in workflow.jobs:
                report.findings.append(Finding(
                    rule_id="unknown_dependency", severity=Severity.ERROR,
                    message=f"Job {job_name!r} depends on unknown job {dep!r}.",
                ))

    return report


# -- Requirements validator ---------------------------------------------


# Subset of historically-vulnerable Python packages with the version
# below which a known CVE was unpatched. Used purely for teaching; in
# production this comes from a CVE feed.
KNOWN_VULNERABLE_PACKAGES: Dict[str, str] = {
    "requests": "2.31.0",
    "urllib3": "2.0.7",
    "pyyaml": "6.0",
    "cryptography": "41.0.6",
    "django": "4.2.10",
}

_PINNED_REQUIREMENT_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.\-]*)==([0-9][0-9A-Za-z_.\-+]*)$"
)


def validate_requirements(content: str) -> ValidationReport:
    """Validate a requirements.txt for pinned versions + known vulns."""
    report = ValidationReport(artifact="requirements.txt")
    seen_packages: Set[str] = set()

    for idx, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-"):  # -e, -r, -c flags
            continue
        match = _PINNED_REQUIREMENT_RE.match(line)
        if not match:
            report.findings.append(Finding(
                rule_id="unpinned_requirement", severity=Severity.ERROR,
                message=f"Requirement not pinned with `==`: {line!r}",
                line=idx,
            ))
            continue
        name = match.group(1).lower()
        version = match.group(2)
        if name in seen_packages:
            report.findings.append(Finding(
                rule_id="duplicate_requirement", severity=Severity.WARNING,
                message=f"Package {name!r} appears more than once.",
                line=idx,
            ))
        seen_packages.add(name)
        vulnerable_below = KNOWN_VULNERABLE_PACKAGES.get(name)
        if vulnerable_below and _version_lt(version, vulnerable_below):
            report.findings.append(Finding(
                rule_id="vulnerable_dependency", severity=Severity.ERROR,
                message=(
                    f"{name}=={version} has known CVEs; pin to "
                    f"{vulnerable_below} or later."
                ),
                line=idx,
            ))

    return report


def _version_lt(a: str, b: str) -> bool:
    """Compare two PEP-440-ish version strings; returns True iff a < b."""
    def _parts(v: str) -> tuple:
        out = []
        for chunk in v.split("."):
            digits = "".join(ch for ch in chunk if ch.isdigit())
            out.append(int(digits) if digits else 0)
        return tuple(out)
    return _parts(a) < _parts(b)


# -- Dockerfile validator -----------------------------------------------


def validate_dockerfile(content: str) -> ValidationReport:
    """Spot-check a Dockerfile for production hygiene."""
    report = ValidationReport(artifact="Dockerfile")
    has_user = False
    has_healthcheck = False
    final_from_line: Optional[int] = None
    final_from_image: Optional[str] = None

    for idx, raw in enumerate(content.splitlines(), start=1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        upper = line.lstrip().upper()
        if upper.startswith("FROM "):
            tokens = line.split()
            final_from_line = idx
            final_from_image = tokens[1] if len(tokens) > 1 else ""
        elif upper.startswith("USER "):
            user_value = line.split(None, 1)[1].strip()
            if user_value not in {"root", "0"}:
                has_user = True
        elif upper.startswith("HEALTHCHECK"):
            has_healthcheck = True

    if final_from_image:
        if ":" not in final_from_image or final_from_image.endswith(":latest"):
            report.findings.append(Finding(
                rule_id="unpinned_base_image", severity=Severity.ERROR,
                message=(
                    f"Base image {final_from_image!r} is not pinned to a "
                    "specific tag (avoid `latest`)."
                ),
                line=final_from_line,
            ))

    if not has_user:
        report.findings.append(Finding(
            rule_id="root_user", severity=Severity.ERROR,
            message="No non-root USER directive found.",
        ))
    if not has_healthcheck:
        report.findings.append(Finding(
            rule_id="missing_healthcheck", severity=Severity.WARNING,
            message="No HEALTHCHECK directive found.",
        ))

    return report
