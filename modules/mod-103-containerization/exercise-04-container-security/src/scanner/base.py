"""
Base types for the container security scanner.

Defines the Vulnerability + ScanResult + SBOM dataclasses and the
abstract Scanner interface that concrete scanners (Trivy, Grype, Snyk)
implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Dict, List, Optional


class Severity(IntEnum):
    UNKNOWN = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def from_string(cls, value: str) -> "Severity":
        try:
            return cls[value.upper()]
        except KeyError:
            return cls.UNKNOWN

    @property
    def display(self) -> str:
        return self.name


@dataclass(frozen=True)
class Vulnerability:
    """A single vulnerability finding."""

    cve_id: str
    package: str
    installed_version: str
    fixed_version: Optional[str]
    severity: Severity
    title: str
    description: str = ""
    references: List[str] = field(default_factory=list)
    layer: Optional[str] = None  # docker layer SHA, if known


@dataclass(frozen=True)
class SecretFinding:
    """A secret detected inside an image layer."""

    type: str  # "aws_access_key", "github_token", etc.
    path: str
    line: int
    match_preview: str
    severity: Severity = Severity.HIGH


@dataclass(frozen=True)
class Misconfiguration:
    """A Dockerfile / image misconfiguration finding."""

    rule_id: str
    title: str
    severity: Severity
    description: str = ""


@dataclass(frozen=True)
class Package:
    """One entry in the SBOM package inventory."""

    name: str
    version: str
    license: Optional[str] = None
    source: str = ""  # "os" / "language:python" / "language:node"
    checksum: Optional[str] = None


@dataclass
class ScanResult:
    """Output of a single scanner run on a single image."""

    image: str
    scanner: str
    scanned_at: datetime
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    secrets: List[SecretFinding] = field(default_factory=list)
    misconfigurations: List[Misconfiguration] = field(default_factory=list)
    packages: List[Package] = field(default_factory=list)

    def severity_counts(self) -> Dict[str, int]:
        counts = {s.display: 0 for s in Severity}
        for v in self.vulnerabilities:
            counts[v.severity.display] += 1
        return counts

    def highest_severity(self) -> Severity:
        if not self.vulnerabilities:
            return Severity.UNKNOWN
        return max(v.severity for v in self.vulnerabilities)


class Scanner(ABC):
    """Abstract base class for image scanners."""

    name: str = "base"

    @abstractmethod
    def scan(self, image: str) -> ScanResult:
        """Run the scan and return a ScanResult."""

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
