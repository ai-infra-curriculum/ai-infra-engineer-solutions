"""
Trivy Scanner Implementation

Wraps the `trivy` CLI to scan container images. The class accepts a
trivy-binary path (default: "trivy") and a JSON-fixture path for offline
use. In CI / classroom mode where Trivy isn't installed, the scanner
reads from a pre-recorded fixture file so tests and demos are
deterministic.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .base import (
    Misconfiguration,
    Package,
    ScanResult,
    Scanner,
    SecretFinding,
    Severity,
    Vulnerability,
)

logger = logging.getLogger(__name__)


class TrivyScanner(Scanner):
    """Container scanner backed by the trivy CLI (or a fixture JSON)."""

    name = "trivy"

    def __init__(
        self,
        *,
        binary: str = "trivy",
        fixture_path: Optional[Path] = None,
        timeout_seconds: int = 600,
    ):
        self.binary = binary
        self.fixture_path = fixture_path
        self.timeout_seconds = timeout_seconds

    def scan(self, image: str) -> ScanResult:
        if self.fixture_path is not None:
            raw = json.loads(Path(self.fixture_path).read_text())
        else:
            raw = self._run_trivy(image)
        return self._parse(image, raw)

    def _run_trivy(self, image: str) -> dict:
        if shutil.which(self.binary) is None:
            raise FileNotFoundError(
                f"Trivy binary {self.binary!r} not on PATH. "
                "Pass fixture_path=… for offline scanning."
            )
        cmd = [
            self.binary, "image", "--format", "json", "--quiet",
            "--scanners", "vuln,secret,misconfig",
            image,
        ]
        logger.info("Running trivy: %s", " ".join(cmd))
        proc = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        return json.loads(proc.stdout)

    def _parse(self, image: str, raw: dict) -> ScanResult:
        result = ScanResult(image=image, scanner=self.name, scanned_at=self._now())
        for entry in raw.get("Results", []):
            target = entry.get("Target", "")
            for v in entry.get("Vulnerabilities", []) or []:
                result.vulnerabilities.append(self._make_vuln(v, target))
            for s in entry.get("Secrets", []) or []:
                result.secrets.append(SecretFinding(
                    type=s.get("RuleID", "unknown"),
                    path=target,
                    line=int(s.get("StartLine", 0)),
                    match_preview=s.get("Match", "")[:80],
                    severity=Severity.from_string(s.get("Severity", "HIGH")),
                ))
            for m in entry.get("Misconfigurations", []) or []:
                result.misconfigurations.append(Misconfiguration(
                    rule_id=m.get("ID", "?"),
                    title=m.get("Title", ""),
                    severity=Severity.from_string(m.get("Severity", "MEDIUM")),
                    description=m.get("Description", ""),
                ))
            for pkg in entry.get("Packages", []) or []:
                result.packages.append(Package(
                    name=pkg.get("Name", "?"),
                    version=pkg.get("Version", "?"),
                    license=(pkg.get("Licenses") or [None])[0],
                    source=f"{entry.get('Type', '')}",
                    checksum=pkg.get("Digest"),
                ))
        return result

    @staticmethod
    def _make_vuln(item: Dict, layer: str) -> Vulnerability:
        return Vulnerability(
            cve_id=item.get("VulnerabilityID", "CVE-UNKNOWN"),
            package=item.get("PkgName", "?"),
            installed_version=item.get("InstalledVersion", "?"),
            fixed_version=item.get("FixedVersion") or None,
            severity=Severity.from_string(item.get("Severity", "UNKNOWN")),
            title=item.get("Title", ""),
            description=item.get("Description", ""),
            references=list(item.get("References", []) or []),
            layer=layer,
        )

    # -- helpers for tests and demos -----------------------------------

    @staticmethod
    def synthetic_result(image: str, *, criticals: int = 0, highs: int = 0) -> ScanResult:
        """Build a deterministic ScanResult for use in tests and demos."""
        result = ScanResult(
            image=image,
            scanner="trivy:synthetic",
            scanned_at=ScannerHelpers.fixed_now(),
        )
        for i in range(criticals):
            result.vulnerabilities.append(Vulnerability(
                cve_id=f"CVE-2024-{1000 + i:04d}",
                package="openssl",
                installed_version="1.1.1k",
                fixed_version="1.1.1l",
                severity=Severity.CRITICAL,
                title="OpenSSL heap overflow",
                description="Synthetic critical vulnerability.",
            ))
        for i in range(highs):
            result.vulnerabilities.append(Vulnerability(
                cve_id=f"CVE-2024-{2000 + i:04d}",
                package="curl",
                installed_version="7.79.0",
                fixed_version="7.79.1",
                severity=Severity.HIGH,
                title="curl auth bypass",
            ))
        result.packages.extend([
            Package(name="openssl", version="1.1.1k", license="OpenSSL", source="os:alpine"),
            Package(name="curl", version="7.79.0", license="MIT", source="os:alpine"),
            Package(name="requests", version="2.31.0", license="Apache-2.0", source="language:python"),
        ])
        return result


class ScannerHelpers:
    @staticmethod
    def fixed_now():
        from datetime import datetime, timezone
        return datetime(2025, 1, 1, tzinfo=timezone.utc)
