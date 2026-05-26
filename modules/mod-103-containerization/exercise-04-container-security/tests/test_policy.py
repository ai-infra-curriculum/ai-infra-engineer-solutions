"""Tests for the policy engine + reporting generators."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.policy.engine import Policy, PolicyEngine
from src.reporting.generator import diff_results, to_html, to_json, to_sarif
from src.scanner.base import (
    Package,
    ScanResult,
    SecretFinding,
    Severity,
    Vulnerability,
    Misconfiguration,
)
from src.scanner.trivy import TrivyScanner


@pytest.fixture
def base_result() -> ScanResult:
    return TrivyScanner.synthetic_result("registry.example.com/app:1.0", criticals=2, highs=1)


@pytest.fixture
def clean_result() -> ScanResult:
    result = TrivyScanner.synthetic_result("registry.example.com/app:1.0")
    return result


class TestPolicyLoading:
    def test_from_dict_defaults(self):
        policy = Policy.from_dict({})
        assert policy.max_severity is Severity.CRITICAL
        assert policy.deny_on_secrets is True

    def test_from_dict_with_blocklist(self):
        policy = Policy.from_dict({
            "max_severity": "HIGH",
            "cve_blocklist": ["CVE-2024-0001"],
            "forbidden_licenses": ["GPL-3.0"],
            "deny_on_secrets": False,
            "deny_on_misconfig_severity": "CRITICAL",
            "require_fixed_version_for_severity": "HIGH",
        })
        assert policy.max_severity is Severity.HIGH
        assert "CVE-2024-0001" in policy.cve_blocklist
        assert "GPL-3.0" in policy.forbidden_licenses
        assert policy.deny_on_secrets is False
        assert policy.deny_on_misconfig_severity is Severity.CRITICAL
        assert policy.require_fixed_version_for_severity is Severity.HIGH

    def test_from_yaml(self, tmp_path: Path):
        p = tmp_path / "policy.yaml"
        p.write_text(
            "max_severity: HIGH\n"
            "cve_blocklist:\n  - CVE-2024-9999\n"
        )
        policy = Policy.from_yaml(p)
        assert policy.max_severity is Severity.HIGH
        assert "CVE-2024-9999" in policy.cve_blocklist


class TestPolicyEngine:
    def test_clean_image_passes_default_policy(self, clean_result: ScanResult):
        # Default policy allows up to CRITICAL; no vulns in clean_result.
        engine = PolicyEngine(Policy())
        decision = engine.evaluate(clean_result)
        assert decision.passed is True
        assert decision.summary["total_vulnerabilities"] == 0

    def test_critical_fails_when_max_is_high(self, base_result: ScanResult):
        policy = Policy(max_severity=Severity.HIGH)
        decision = PolicyEngine(policy).evaluate(base_result)
        assert decision.passed is False
        assert any(v.rule == "max_severity" for v in decision.violations)

    def test_cve_allowlist_suppresses_violation(self, base_result: ScanResult):
        # Allow both critical CVEs and lower the max severity to HIGH.
        policy = Policy(
            max_severity=Severity.HIGH,
            cve_allowlist={"CVE-2024-1000", "CVE-2024-1001"},
        )
        decision = PolicyEngine(policy).evaluate(base_result)
        # max_severity rule suppressed by allowlist, but the HIGH vulnerability
        # remains within the threshold, so should pass.
        assert decision.passed is True

    def test_cve_blocklist_fires(self, base_result: ScanResult):
        policy = Policy(
            max_severity=Severity.CRITICAL,
            cve_blocklist={"CVE-2024-2000"},
        )
        decision = PolicyEngine(policy).evaluate(base_result)
        assert any(v.rule == "cve_blocklist" for v in decision.violations)

    def test_forbidden_license_fails(self):
        result = ScanResult(image="x", scanner="t", scanned_at=datetime.now(timezone.utc))
        result.packages.append(Package(name="lib", version="1.0", license="GPL-3.0"))
        policy = Policy(forbidden_licenses={"GPL-3.0"})
        decision = PolicyEngine(policy).evaluate(result)
        assert any(v.rule == "forbidden_license" for v in decision.violations)

    def test_secrets_block_by_default(self):
        result = ScanResult(image="x", scanner="t", scanned_at=datetime.now(timezone.utc))
        result.secrets.append(SecretFinding(
            type="aws", path=".env", line=1, match_preview="AKIA...",
        ))
        decision = PolicyEngine(Policy()).evaluate(result)
        assert any(v.rule == "secret_in_image" for v in decision.violations)

    def test_secrets_allowed_when_policy_relaxed(self):
        result = ScanResult(image="x", scanner="t", scanned_at=datetime.now(timezone.utc))
        result.secrets.append(SecretFinding(
            type="aws", path=".env", line=1, match_preview="AKIA...",
        ))
        decision = PolicyEngine(Policy(deny_on_secrets=False)).evaluate(result)
        assert not any(v.rule == "secret_in_image" for v in decision.violations)

    def test_misconfig_threshold_filters(self):
        result = ScanResult(image="x", scanner="t", scanned_at=datetime.now(timezone.utc))
        result.misconfigurations.append(Misconfiguration(
            rule_id="DS001", title="root user", severity=Severity.MEDIUM,
        ))
        # Threshold is HIGH by default → MEDIUM not blocked.
        decision = PolicyEngine(Policy()).evaluate(result)
        assert not any(v.rule == "misconfiguration" for v in decision.violations)

        decision = PolicyEngine(Policy(deny_on_misconfig_severity=Severity.MEDIUM)).evaluate(result)
        assert any(v.rule == "misconfiguration" for v in decision.violations)

    def test_forbidden_base_image_pattern(self, base_result: ScanResult):
        policy = Policy(forbidden_base_images=[r"registry\.example\.com/.*"])
        decision = PolicyEngine(policy).evaluate(base_result)
        assert any(v.rule == "forbidden_base_image" for v in decision.violations)

    def test_allowlist_misses_block(self, base_result: ScanResult):
        policy = Policy(allowed_base_images=[r"trusted-registry\.com/.*"])
        decision = PolicyEngine(policy).evaluate(base_result)
        assert any(v.rule == "base_image_not_in_allowlist" for v in decision.violations)

    def test_require_fixed_version_blocks_unfixable(self):
        result = ScanResult(image="x", scanner="t", scanned_at=datetime.now(timezone.utc))
        result.vulnerabilities.append(Vulnerability(
            cve_id="CVE-XYZ", package="lib", installed_version="1.0",
            fixed_version=None, severity=Severity.HIGH, title="t",
        ))
        policy = Policy(require_fixed_version_for_severity=Severity.HIGH)
        decision = PolicyEngine(policy).evaluate(result)
        assert any(v.rule == "fix_available" for v in decision.violations)


class TestReportGenerators:
    def test_json_round_trips(self, base_result: ScanResult):
        body = to_json(base_result, decision=None)
        parsed = json.loads(body)
        assert parsed["scan"]["image"] == base_result.image
        assert len(parsed["scan"]["vulnerabilities"]) == 3

    def test_sarif_has_results_and_rules(self, base_result: ScanResult):
        body = to_sarif(base_result)
        parsed = json.loads(body)
        assert parsed["version"] == "2.1.0"
        run = parsed["runs"][0]
        assert run["tool"]["driver"]["name"] == "containersec"
        assert len(run["results"]) == 3

    def test_html_contains_image_and_critical_class(self, base_result: ScanResult):
        body = to_html(base_result, decision=None)
        assert base_result.image in body
        assert "sev-critical" in body

    def test_diff_introduced_and_fixed(self):
        older = ScanResult(image="x", scanner="t", scanned_at=datetime.now(timezone.utc))
        older.vulnerabilities.append(Vulnerability(
            cve_id="CVE-A", package="p", installed_version="1.0",
            fixed_version=None, severity=Severity.HIGH, title="t",
        ))
        older.vulnerabilities.append(Vulnerability(
            cve_id="CVE-B", package="q", installed_version="1.0",
            fixed_version=None, severity=Severity.MEDIUM, title="t",
        ))
        newer = ScanResult(image="x", scanner="t", scanned_at=datetime.now(timezone.utc))
        newer.vulnerabilities.append(Vulnerability(
            cve_id="CVE-B", package="q", installed_version="1.0",
            fixed_version=None, severity=Severity.MEDIUM, title="t",
        ))
        newer.vulnerabilities.append(Vulnerability(
            cve_id="CVE-C", package="r", installed_version="1.0",
            fixed_version=None, severity=Severity.LOW, title="t",
        ))
        delta = diff_results(older, newer)
        assert delta["introduced_count"] == 1
        assert delta["fixed_count"] == 1
        assert delta["introduced"][0]["cve_id"] == "CVE-C"
        assert delta["fixed"][0]["cve_id"] == "CVE-A"
