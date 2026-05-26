"""
Security Policy Engine

Evaluate a ScanResult against a declarative policy:

- Maximum allowed severity (e.g., block CRITICAL).
- CVE blocklist (e.g., specific known-bad CVEs).
- License restrictions (e.g., no GPL-3.0 in commercial images).
- Base image restrictions (allowed / disallowed base image names).
- Secrets policy (any secret = block).

Policies are loaded from YAML. The engine returns a structured
PolicyDecision that the CLI uses to drive pass/fail and produce an
actionable report.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

from ..scanner.base import ScanResult, Severity, Vulnerability

logger = logging.getLogger(__name__)


@dataclass
class Policy:
    """Declarative security policy."""

    max_severity: Severity = Severity.CRITICAL
    cve_blocklist: Set[str] = field(default_factory=set)
    cve_allowlist: Set[str] = field(default_factory=set)
    forbidden_licenses: Set[str] = field(default_factory=set)
    allowed_base_images: List[str] = field(default_factory=list)
    forbidden_base_images: List[str] = field(default_factory=list)
    deny_on_secrets: bool = True
    deny_on_misconfig_severity: Optional[Severity] = Severity.HIGH
    require_fixed_version_for_severity: Optional[Severity] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "Policy":
        return cls(
            max_severity=Severity.from_string(data.get("max_severity", "CRITICAL")),
            cve_blocklist=set(data.get("cve_blocklist", []) or []),
            cve_allowlist=set(data.get("cve_allowlist", []) or []),
            forbidden_licenses=set(data.get("forbidden_licenses", []) or []),
            allowed_base_images=list(data.get("allowed_base_images", []) or []),
            forbidden_base_images=list(data.get("forbidden_base_images", []) or []),
            deny_on_secrets=bool(data.get("deny_on_secrets", True)),
            deny_on_misconfig_severity=(
                Severity.from_string(data["deny_on_misconfig_severity"])
                if data.get("deny_on_misconfig_severity")
                else None
            ),
            require_fixed_version_for_severity=(
                Severity.from_string(data["require_fixed_version_for_severity"])
                if data.get("require_fixed_version_for_severity")
                else None
            ),
        )

    @classmethod
    def from_yaml(cls, path: Path) -> "Policy":
        return cls.from_dict(yaml.safe_load(Path(path).read_text()))


@dataclass
class Violation:
    rule: str
    detail: str
    severity: Severity


@dataclass
class PolicyDecision:
    image: str
    passed: bool
    violations: List[Violation]
    summary: Dict[str, int]

    def to_dict(self) -> Dict:
        return {
            "image": self.image,
            "passed": self.passed,
            "violations": [
                {"rule": v.rule, "detail": v.detail, "severity": v.severity.display}
                for v in self.violations
            ],
            "summary": self.summary,
        }


class PolicyEngine:
    """Evaluate ScanResults against a Policy."""

    def __init__(self, policy: Policy):
        self.policy = policy

    def evaluate(self, result: ScanResult) -> PolicyDecision:
        violations: List[Violation] = []
        violations.extend(self._check_severity(result))
        violations.extend(self._check_cve_blocklist(result))
        violations.extend(self._check_licenses(result))
        violations.extend(self._check_base_image(result))
        violations.extend(self._check_secrets(result))
        violations.extend(self._check_misconfigurations(result))
        violations.extend(self._check_fixed_version(result))

        summary = {
            "total_vulnerabilities": len(result.vulnerabilities),
            **result.severity_counts(),
            "secrets": len(result.secrets),
            "misconfigurations": len(result.misconfigurations),
            "violations": len(violations),
        }
        return PolicyDecision(
            image=result.image,
            passed=not violations,
            violations=violations,
            summary=summary,
        )

    # -- individual checks ---------------------------------------------

    def _check_severity(self, result: ScanResult) -> List[Violation]:
        violations: List[Violation] = []
        for v in result.vulnerabilities:
            if v.cve_id in self.policy.cve_allowlist:
                continue
            if v.severity > self.policy.max_severity:
                violations.append(Violation(
                    rule="max_severity",
                    detail=f"{v.cve_id} on {v.package}@{v.installed_version} is {v.severity.display}",
                    severity=v.severity,
                ))
        return violations

    def _check_cve_blocklist(self, result: ScanResult) -> List[Violation]:
        if not self.policy.cve_blocklist:
            return []
        return [
            Violation(
                rule="cve_blocklist",
                detail=f"Blocklisted CVE {v.cve_id} on {v.package}@{v.installed_version}",
                severity=v.severity,
            )
            for v in result.vulnerabilities
            if v.cve_id in self.policy.cve_blocklist
        ]

    def _check_licenses(self, result: ScanResult) -> List[Violation]:
        if not self.policy.forbidden_licenses:
            return []
        return [
            Violation(
                rule="forbidden_license",
                detail=f"Package {pkg.name}@{pkg.version} uses forbidden license {pkg.license}",
                severity=Severity.HIGH,
            )
            for pkg in result.packages
            if pkg.license and pkg.license in self.policy.forbidden_licenses
        ]

    def _check_base_image(self, result: ScanResult) -> List[Violation]:
        violations: List[Violation] = []
        for forbidden in self.policy.forbidden_base_images:
            if re.match(forbidden, result.image):
                violations.append(Violation(
                    rule="forbidden_base_image",
                    detail=f"Image {result.image} matches forbidden pattern {forbidden}",
                    severity=Severity.HIGH,
                ))
                return violations  # one match is enough
        if self.policy.allowed_base_images and not any(
            re.match(p, result.image) for p in self.policy.allowed_base_images
        ):
            violations.append(Violation(
                rule="base_image_not_in_allowlist",
                detail=(
                    f"Image {result.image} does not match any allowed base image "
                    f"({self.policy.allowed_base_images})"
                ),
                severity=Severity.HIGH,
            ))
        return violations

    def _check_secrets(self, result: ScanResult) -> List[Violation]:
        if not self.policy.deny_on_secrets:
            return []
        return [
            Violation(
                rule="secret_in_image",
                detail=f"{secret.type} found at {secret.path}:{secret.line}",
                severity=secret.severity,
            )
            for secret in result.secrets
        ]

    def _check_misconfigurations(self, result: ScanResult) -> List[Violation]:
        if self.policy.deny_on_misconfig_severity is None:
            return []
        return [
            Violation(
                rule="misconfiguration",
                detail=f"{misc.rule_id}: {misc.title}",
                severity=misc.severity,
            )
            for misc in result.misconfigurations
            if misc.severity >= self.policy.deny_on_misconfig_severity
        ]

    def _check_fixed_version(self, result: ScanResult) -> List[Violation]:
        threshold = self.policy.require_fixed_version_for_severity
        if threshold is None:
            return []
        return [
            Violation(
                rule="fix_available",
                detail=(
                    f"{v.cve_id} on {v.package}@{v.installed_version} "
                    f"has no fixed version but severity is {v.severity.display}"
                ),
                severity=v.severity,
            )
            for v in result.vulnerabilities
            if v.severity >= threshold and not v.fixed_version
        ]
