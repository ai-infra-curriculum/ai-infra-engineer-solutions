"""
Container Security Scanner - CLI Entry Point

Scan container images, evaluate them against a security policy, and
emit a JSON / SARIF / HTML report. Uses the Trivy scanner; pass
--fixture path/to.json to run from a pre-recorded scan when Trivy isn't
installed locally.

Subcommands:
    scan    Scan an image and emit a report.
    sbom    Emit a CycloneDX/SPDX/Syft SBOM for an image.
    diff    Compare two saved JSON scans, listing introduced and fixed CVEs.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .policy.engine import Policy, PolicyEngine
from .reporting.generator import diff_results, to_html, to_json, to_sarif
from .scanner.aggregator import to_cyclonedx, to_spdx, to_syft
from .scanner.base import (
    Package,
    ScanResult,
    Severity,
    Vulnerability,
)
from .scanner.trivy import TrivyScanner


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Container Security Scanner."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.argument("image")
@click.option("--fixture", type=click.Path(exists=True, dir_okay=False))
@click.option("--policy", "policy_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--format", "fmt",
    default="text",
    type=click.Choice(["text", "json", "sarif", "html"]),
)
@click.option("--output", type=click.Path(dir_okay=False))
@click.option("--synthetic-criticals", type=int, default=None, hidden=True)
@click.option("--synthetic-highs", type=int, default=None, hidden=True)
def scan(
    image: str,
    fixture: Optional[str],
    policy_path: Optional[str],
    fmt: str,
    output: Optional[str],
    synthetic_criticals: Optional[int],
    synthetic_highs: Optional[int],
) -> None:
    """Scan an image, evaluate policy, emit report."""
    if synthetic_criticals is not None or synthetic_highs is not None:
        result = TrivyScanner.synthetic_result(
            image,
            criticals=synthetic_criticals or 0,
            highs=synthetic_highs or 0,
        )
    else:
        scanner = TrivyScanner(fixture_path=Path(fixture) if fixture else None)
        result = scanner.scan(image)

    decision = None
    if policy_path:
        policy = Policy.from_yaml(Path(policy_path))
        decision = PolicyEngine(policy).evaluate(result)

    if fmt == "json":
        body = to_json(result, decision)
    elif fmt == "sarif":
        body = to_sarif(result)
    elif fmt == "html":
        body = to_html(result, decision)
    else:
        body = _format_text(result, decision)

    if output:
        Path(output).write_text(body)
        click.echo(f"Report written to {output}")
    else:
        click.echo(body)

    if decision and not decision.passed:
        sys.exit(2)


@cli.command()
@click.argument("image")
@click.option("--fixture", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--format", "fmt",
    default="cyclonedx",
    type=click.Choice(["cyclonedx", "spdx", "syft"]),
)
@click.option("--output", type=click.Path(dir_okay=False))
@click.option("--synthetic-criticals", type=int, default=None, hidden=True)
def sbom(
    image: str,
    fixture: Optional[str],
    fmt: str,
    output: Optional[str],
    synthetic_criticals: Optional[int],
) -> None:
    """Emit an SBOM in the requested format."""
    if synthetic_criticals is not None:
        result = TrivyScanner.synthetic_result(image, criticals=synthetic_criticals or 0)
    else:
        scanner = TrivyScanner(fixture_path=Path(fixture) if fixture else None)
        result = scanner.scan(image)
    renderers = {
        "cyclonedx": to_cyclonedx,
        "spdx": to_spdx,
        "syft": to_syft,
    }
    body = json.dumps(renderers[fmt](result), indent=2)
    if output:
        Path(output).write_text(body)
        click.echo(f"SBOM written to {output}")
    else:
        click.echo(body)


@cli.command()
@click.argument("older", type=click.Path(exists=True, dir_okay=False))
@click.argument("newer", type=click.Path(exists=True, dir_okay=False))
def diff(older: str, newer: str) -> None:
    """Diff two saved scan JSON files."""
    older_result = _load_scan(Path(older))
    newer_result = _load_scan(Path(newer))
    delta = diff_results(older_result, newer_result)
    click.echo(json.dumps(delta, indent=2))


# -- helpers ----------------------------------------------------------


def _format_text(result: ScanResult, decision) -> str:
    lines = [
        f"Image: {result.image}",
        f"Scanner: {result.scanner}",
        f"Scanned at: {result.scanned_at.isoformat(timespec='seconds')}",
        "Severity counts:",
    ]
    counts = result.severity_counts()
    for name, value in counts.items():
        if value:
            lines.append(f"  {name:<10s} {value}")
    if not any(counts.values()):
        lines.append("  (none)")
    if decision:
        lines.append("")
        lines.append(f"Policy: {'PASS' if decision.passed else 'FAIL'}")
        for v in decision.violations:
            lines.append(f"  - [{v.severity.display}] {v.rule}: {v.detail}")
    return "\n".join(lines)


def _load_scan(path: Path) -> ScanResult:
    """Reconstruct a minimal ScanResult from a saved JSON report."""
    data = json.loads(path.read_text())
    scan = data.get("scan", data)
    from datetime import datetime
    result = ScanResult(
        image=scan["image"],
        scanner=scan.get("scanner", "loaded"),
        scanned_at=datetime.fromisoformat(scan["scanned_at"]),
    )
    for v in scan.get("vulnerabilities", []):
        result.vulnerabilities.append(Vulnerability(
            cve_id=v["cve_id"],
            package=v["package"],
            installed_version=v["installed_version"],
            fixed_version=v.get("fixed_version"),
            severity=Severity.from_string(v.get("severity", "UNKNOWN")),
            title=v.get("title", ""),
            description=v.get("description", ""),
            references=list(v.get("references", [])),
            layer=v.get("layer"),
        ))
    for p in scan.get("packages", []):
        result.packages.append(Package(
            name=p["name"],
            version=p["version"],
            license=p.get("license"),
            source=p.get("source", ""),
            checksum=p.get("checksum"),
        ))
    return result


if __name__ == "__main__":
    cli()
