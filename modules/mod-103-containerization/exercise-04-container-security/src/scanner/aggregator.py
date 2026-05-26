"""
Scan Aggregator

Run multiple scanners (Trivy + Grype + Snyk) over the same image and
merge their findings, deduplicating by (CVE, package, installed_version)
and reconciling severity by taking the highest reported value.

Also produces SBOM exports in CycloneDX, SPDX, and Syft formats from
the merged package inventory.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from .base import Package, ScanResult, Scanner, Severity, Vulnerability

logger = logging.getLogger(__name__)


class ScanAggregator:
    """Merge results across multiple scanners."""

    def __init__(self, scanners: Iterable[Scanner]):
        self.scanners = list(scanners)
        if not self.scanners:
            raise ValueError("ScanAggregator requires at least one scanner")

    def scan(self, image: str) -> ScanResult:
        results = [s.scan(image) for s in self.scanners]
        return self.merge(image, results)

    @staticmethod
    def merge(image: str, results: List[ScanResult]) -> ScanResult:
        if not results:
            raise ValueError("No scan results to merge")
        scanners = ",".join(sorted({r.scanner for r in results}))
        merged = ScanResult(
            image=image,
            scanner=f"aggregator[{scanners}]",
            scanned_at=datetime.now(timezone.utc),
        )

        vuln_index: Dict[Tuple[str, str, str], Vulnerability] = {}
        for r in results:
            for v in r.vulnerabilities:
                key = (v.cve_id, v.package, v.installed_version)
                existing = vuln_index.get(key)
                if existing is None or v.severity > existing.severity:
                    vuln_index[key] = v
        merged.vulnerabilities = list(vuln_index.values())

        # Deduplicate packages by (name, version, source).
        pkg_index: Dict[Tuple[str, str, str], Package] = {}
        for r in results:
            for pkg in r.packages:
                pkg_index[(pkg.name, pkg.version, pkg.source)] = pkg
        merged.packages = list(pkg_index.values())

        # Aggregate secrets + misconfigurations as union (cheap dedup by str).
        seen_secrets = set()
        for r in results:
            for s in r.secrets:
                key = (s.type, s.path, s.line)
                if key in seen_secrets:
                    continue
                seen_secrets.add(key)
                merged.secrets.append(s)

        seen_misc = set()
        for r in results:
            for m in r.misconfigurations:
                if m.rule_id in seen_misc:
                    continue
                seen_misc.add(m.rule_id)
                merged.misconfigurations.append(m)

        return merged


# -- SBOM exporters -----------------------------------------------------


def to_cyclonedx(result: ScanResult) -> dict:
    """Render the package inventory as a CycloneDX 1.5 document."""
    components = []
    for pkg in result.packages:
        components.append({
            "type": "library",
            "bom-ref": f"{pkg.name}@{pkg.version}",
            "name": pkg.name,
            "version": pkg.version,
            **({"licenses": [{"license": {"id": pkg.license}}]} if pkg.license else {}),
            **({"hashes": [{"alg": "SHA-256", "content": pkg.checksum}]} if pkg.checksum else {}),
        })
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": result.scanned_at.isoformat(),
            "component": {"type": "container", "name": result.image},
        },
        "components": components,
    }


def to_spdx(result: ScanResult) -> dict:
    """Render the package inventory as a minimal SPDX 2.3 document."""
    packages = []
    relationships = []
    document_spdx_id = "SPDXRef-DOCUMENT"
    image_spdx_id = "SPDXRef-Image"
    packages.append({
        "SPDXID": image_spdx_id,
        "name": result.image,
        "downloadLocation": "NOASSERTION",
        "licenseConcluded": "NOASSERTION",
    })
    for i, pkg in enumerate(result.packages):
        spdx_id = f"SPDXRef-Package-{i}"
        packages.append({
            "SPDXID": spdx_id,
            "name": pkg.name,
            "versionInfo": pkg.version,
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": pkg.license or "NOASSERTION",
        })
        relationships.append({
            "spdxElementId": image_spdx_id,
            "relatedSpdxElement": spdx_id,
            "relationshipType": "CONTAINS",
        })
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": document_spdx_id,
        "name": f"sbom-{result.image}",
        "documentNamespace": f"https://example.com/sbom/{uuid.uuid4()}",
        "creationInfo": {
            "created": result.scanned_at.isoformat(),
            "creators": ["Tool: containersec"],
        },
        "packages": packages,
        "relationships": relationships,
    }


def to_syft(result: ScanResult) -> dict:
    """Render the package inventory as the Syft native JSON format."""
    artifacts = []
    for pkg in result.packages:
        artifacts.append({
            "name": pkg.name,
            "version": pkg.version,
            "type": pkg.source or "unknown",
            "licenses": [pkg.license] if pkg.license else [],
            "metadata": {"checksum": pkg.checksum} if pkg.checksum else {},
        })
    return {
        "schema": {"version": "11.0.0", "url": "https://github.com/anchore/syft"},
        "artifacts": artifacts,
        "source": {"type": "image", "target": result.image},
        "descriptor": {"name": "containersec", "version": "1.0.0"},
        "timestamp": result.scanned_at.isoformat(),
    }
