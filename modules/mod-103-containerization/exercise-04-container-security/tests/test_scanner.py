"""Tests for the scanner package."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.scanner.aggregator import (
    ScanAggregator,
    to_cyclonedx,
    to_spdx,
    to_syft,
)
from src.scanner.base import (
    Misconfiguration,
    Package,
    ScanResult,
    Scanner,
    SecretFinding,
    Severity,
    Vulnerability,
)
from src.scanner.trivy import TrivyScanner


FIXTURE = {
    "Results": [
        {
            "Target": "alpine:3.16 (alpine 3.16.0)",
            "Type": "alpine",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2023-0001",
                    "PkgName": "openssl",
                    "InstalledVersion": "1.1.1k",
                    "FixedVersion": "1.1.1l",
                    "Severity": "CRITICAL",
                    "Title": "OpenSSL heap overflow",
                    "References": ["https://example.com/cve-2023-0001"],
                },
                {
                    "VulnerabilityID": "CVE-2023-0002",
                    "PkgName": "curl",
                    "InstalledVersion": "7.79.0",
                    "FixedVersion": "7.79.1",
                    "Severity": "HIGH",
                    "Title": "curl auth bypass",
                },
            ],
            "Secrets": [
                {"RuleID": "aws-access-key", "StartLine": 12,
                 "Match": "AKIAIOSFODNN7EXAMPLE", "Severity": "HIGH"},
            ],
            "Misconfigurations": [
                {"ID": "DS001", "Title": "Image runs as root",
                 "Severity": "HIGH", "Description": "Image lacks USER instruction."},
            ],
            "Packages": [
                {"Name": "openssl", "Version": "1.1.1k", "Licenses": ["OpenSSL"]},
                {"Name": "curl", "Version": "7.79.0", "Licenses": ["MIT"]},
            ],
        },
    ],
}


@pytest.fixture
def fixture_path(tmp_path: Path) -> Path:
    p = tmp_path / "trivy.json"
    p.write_text(json.dumps(FIXTURE))
    return p


@pytest.fixture
def scanner(fixture_path: Path) -> TrivyScanner:
    return TrivyScanner(fixture_path=fixture_path)


class TestSeverity:
    def test_from_string_known_value(self):
        assert Severity.from_string("CRITICAL") is Severity.CRITICAL
        assert Severity.from_string("high") is Severity.HIGH

    def test_from_string_unknown(self):
        assert Severity.from_string("imaginary") is Severity.UNKNOWN

    def test_ordering(self):
        assert Severity.CRITICAL > Severity.HIGH > Severity.MEDIUM > Severity.LOW


class TestTrivyScanner:
    def test_fixture_round_trip(self, scanner: TrivyScanner):
        result = scanner.scan("alpine:3.16")
        assert result.image == "alpine:3.16"
        assert result.scanner == "trivy"
        assert len(result.vulnerabilities) == 2
        assert len(result.secrets) == 1
        assert len(result.misconfigurations) == 1
        assert len(result.packages) == 2

    def test_vulnerability_fields_parsed(self, scanner: TrivyScanner):
        result = scanner.scan("alpine:3.16")
        critical = next(v for v in result.vulnerabilities if v.severity is Severity.CRITICAL)
        assert critical.cve_id == "CVE-2023-0001"
        assert critical.fixed_version == "1.1.1l"
        assert critical.references == ["https://example.com/cve-2023-0001"]

    def test_severity_counts(self, scanner: TrivyScanner):
        result = scanner.scan("alpine:3.16")
        counts = result.severity_counts()
        assert counts["CRITICAL"] == 1
        assert counts["HIGH"] == 1
        assert counts["LOW"] == 0

    def test_highest_severity(self, scanner: TrivyScanner):
        result = scanner.scan("alpine:3.16")
        assert result.highest_severity() is Severity.CRITICAL

    def test_missing_binary_with_no_fixture_raises(self):
        scanner = TrivyScanner(binary="trivy-does-not-exist")
        with pytest.raises(FileNotFoundError):
            scanner.scan("alpine:3.16")

    def test_synthetic_result_has_expected_counts(self):
        result = TrivyScanner.synthetic_result("test:latest", criticals=2, highs=3)
        assert len([v for v in result.vulnerabilities if v.severity is Severity.CRITICAL]) == 2
        assert len([v for v in result.vulnerabilities if v.severity is Severity.HIGH]) == 3


class _FakeScanner(Scanner):
    name = "fake"

    def __init__(self, result: ScanResult):
        self._result = result

    def scan(self, image: str) -> ScanResult:
        return self._result


class TestScanAggregator:
    def test_requires_at_least_one_scanner(self):
        with pytest.raises(ValueError):
            ScanAggregator([])

    def test_merges_disjoint_findings(self):
        r1 = ScanResult(image="x", scanner="a", scanned_at=datetime.now(timezone.utc))
        r1.vulnerabilities.append(Vulnerability(
            cve_id="CVE-1", package="p", installed_version="1.0",
            fixed_version=None, severity=Severity.HIGH, title="t",
        ))
        r2 = ScanResult(image="x", scanner="b", scanned_at=datetime.now(timezone.utc))
        r2.vulnerabilities.append(Vulnerability(
            cve_id="CVE-2", package="q", installed_version="1.0",
            fixed_version=None, severity=Severity.MEDIUM, title="t",
        ))
        merged = ScanAggregator.merge("x", [r1, r2])
        assert len(merged.vulnerabilities) == 2

    def test_dedupes_overlapping_and_keeps_highest_severity(self):
        r1 = ScanResult(image="x", scanner="a", scanned_at=datetime.now(timezone.utc))
        r2 = ScanResult(image="x", scanner="b", scanned_at=datetime.now(timezone.utc))
        common = dict(cve_id="CVE-X", package="p", installed_version="1.0",
                      fixed_version="1.1", title="t")
        r1.vulnerabilities.append(Vulnerability(severity=Severity.MEDIUM, **common))
        r2.vulnerabilities.append(Vulnerability(severity=Severity.CRITICAL, **common))
        merged = ScanAggregator.merge("x", [r1, r2])
        assert len(merged.vulnerabilities) == 1
        assert merged.vulnerabilities[0].severity is Severity.CRITICAL

    def test_dedupes_secrets_by_path_and_line(self):
        r1 = ScanResult(image="x", scanner="a", scanned_at=datetime.now(timezone.utc))
        r2 = ScanResult(image="x", scanner="b", scanned_at=datetime.now(timezone.utc))
        s = SecretFinding(type="aws", path="/app/.env", line=3, match_preview="AK...")
        r1.secrets.append(s)
        r2.secrets.append(s)
        merged = ScanAggregator.merge("x", [r1, r2])
        assert len(merged.secrets) == 1

    def test_dedupes_misconfigurations_by_rule_id(self):
        r1 = ScanResult(image="x", scanner="a", scanned_at=datetime.now(timezone.utc))
        r2 = ScanResult(image="x", scanner="b", scanned_at=datetime.now(timezone.utc))
        m = Misconfiguration(rule_id="DS001", title="t", severity=Severity.HIGH)
        r1.misconfigurations.append(m)
        r2.misconfigurations.append(m)
        merged = ScanAggregator.merge("x", [r1, r2])
        assert len(merged.misconfigurations) == 1

    def test_scan_invokes_all_scanners(self, fixture_path):
        scanner_one = _FakeScanner(TrivyScanner(fixture_path=fixture_path).scan("img"))
        scanner_two = _FakeScanner(TrivyScanner.synthetic_result("img", criticals=1))
        merged = ScanAggregator([scanner_one, scanner_two]).scan("img")
        # 2 vulns from fixture + 1 distinct critical from synthetic
        assert len(merged.vulnerabilities) == 3


class TestSBOMExporters:
    def test_cyclonedx_format(self, scanner: TrivyScanner):
        result = scanner.scan("alpine:3.16")
        sbom = to_cyclonedx(result)
        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.5"
        assert len(sbom["components"]) == 2
        assert sbom["components"][0]["type"] == "library"

    def test_spdx_format(self, scanner: TrivyScanner):
        result = scanner.scan("alpine:3.16")
        sbom = to_spdx(result)
        assert sbom["spdxVersion"] == "SPDX-2.3"
        # 1 image entry + 2 package entries
        assert len(sbom["packages"]) == 3
        assert len(sbom["relationships"]) == 2

    def test_syft_format(self, scanner: TrivyScanner):
        result = scanner.scan("alpine:3.16")
        sbom = to_syft(result)
        assert sbom["source"]["type"] == "image"
        assert sbom["source"]["target"] == "alpine:3.16"
        assert len(sbom["artifacts"]) == 2
