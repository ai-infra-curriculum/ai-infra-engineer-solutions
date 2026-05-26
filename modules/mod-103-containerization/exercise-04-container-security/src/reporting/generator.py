"""
Security Report Generators

Render scan + policy decisions in three formats:
- JSON (machine-readable, fully detailed)
- SARIF (GitHub Code Scanning compatible)
- HTML (self-contained, no JS framework)
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Optional

from ..policy.engine import PolicyDecision
from ..scanner.base import ScanResult, Severity


def to_json(
    result: ScanResult,
    decision: Optional[PolicyDecision] = None,
    *,
    indent: int = 2,
) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scan": _scan_to_dict(result),
        "policy": decision.to_dict() if decision else None,
    }
    return json.dumps(payload, indent=indent)


def to_sarif(result: ScanResult) -> str:
    """Render in SARIF v2.1.0 (GitHub Code Scanning format)."""
    rules = {}
    results_list = []
    for v in result.vulnerabilities:
        rule_id = v.cve_id
        rules[rule_id] = {
            "id": rule_id,
            "name": v.cve_id,
            "shortDescription": {"text": v.title or v.cve_id},
            "fullDescription": {"text": v.description or v.title or v.cve_id},
            "helpUri": v.references[0] if v.references else "",
            "properties": {"security-severity": _security_severity(v.severity)},
        }
        results_list.append({
            "ruleId": rule_id,
            "level": _sarif_level(v.severity),
            "message": {
                "text": (
                    f"{v.cve_id}: {v.package} {v.installed_version}"
                    + (f" → {v.fixed_version}" if v.fixed_version else "")
                ),
            },
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": v.layer or result.image},
                },
            }],
        })
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "containersec",
                    "version": "1.0.0",
                    "rules": list(rules.values()),
                },
            },
            "results": results_list,
        }],
    }, indent=2)


def to_html(
    result: ScanResult,
    decision: Optional[PolicyDecision] = None,
) -> str:
    counts = result.severity_counts()
    status = (
        "<span class=pass>PASS</span>"
        if decision and decision.passed
        else "<span class=fail>FAIL</span>"
        if decision
        else "<span>—</span>"
    )
    rows = ""
    for v in sorted(result.vulnerabilities, key=lambda x: -int(x.severity)):
        rows += (
            "<tr>"
            f"<td class=sev-{v.severity.display.lower()}>{v.severity.display}</td>"
            f"<td>{html.escape(v.cve_id)}</td>"
            f"<td>{html.escape(v.package)}</td>"
            f"<td>{html.escape(v.installed_version)}</td>"
            f"<td>{html.escape(v.fixed_version or '—')}</td>"
            f"<td>{html.escape(v.title)}</td>"
            "</tr>"
        )
    viol_rows = ""
    if decision:
        for v in decision.violations:
            viol_rows += (
                "<tr>"
                f"<td>{html.escape(v.rule)}</td>"
                f"<td class=sev-{v.severity.display.lower()}>{v.severity.display}</td>"
                f"<td>{html.escape(v.detail)}</td>"
                "</tr>"
            )
    return (
        "<!doctype html>\n<html><head><meta charset=utf-8>"
        f"<title>Security report — {html.escape(result.image)}</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;margin:2rem;max-width:1100px}"
        "h1,h2{color:#222}"
        ".pass{color:#0a7;font-weight:600}.fail{color:#c33;font-weight:600}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0}"
        "th,td{padding:.45rem .6rem;border-bottom:1px solid #ddd;text-align:left}"
        "th{background:#f4f4f4}"
        ".sev-critical{background:#fde0e0;font-weight:600}"
        ".sev-high{background:#ffe9c2}"
        ".sev-medium{background:#fff5c2}"
        ".sev-low{background:#e7f4e7}"
        ".sev-unknown{color:#888}"
        ".pill{display:inline-block;padding:.2rem .55rem;border-radius:1rem;"
        "background:#eef;margin-right:.5rem}"
        "</style></head><body>"
        f"<h1>Security Report — {html.escape(result.image)}</h1>"
        f"<p>Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}</p>"
        f"<p>Policy decision: {status}</p>"
        "<p>"
        + "".join(
            f"<span class=pill>{name}: {value}</span>"
            for name, value in counts.items() if value
        )
        + "</p>"
        + (f"<h2>Policy violations ({len(decision.violations)})</h2>"
           "<table><thead><tr><th>Rule</th><th>Severity</th><th>Detail</th></tr></thead><tbody>"
           + viol_rows + "</tbody></table>"
           if decision and decision.violations
           else "")
        + "<h2>Vulnerabilities</h2>"
        "<table><thead><tr>"
        "<th>Severity</th><th>CVE</th><th>Package</th>"
        "<th>Installed</th><th>Fixed</th><th>Title</th>"
        "</tr></thead><tbody>"
        + rows
        + "</tbody></table>"
        + "</body></html>"
    )


def diff_results(
    older: ScanResult,
    newer: ScanResult,
) -> dict:
    """Compute the set of newly-introduced and newly-fixed vulnerabilities."""
    def _key(v):
        return (v.cve_id, v.package, v.installed_version)
    older_keys = {_key(v): v for v in older.vulnerabilities}
    newer_keys = {_key(v): v for v in newer.vulnerabilities}
    introduced = [newer_keys[k] for k in newer_keys.keys() - older_keys.keys()]
    fixed = [older_keys[k] for k in older_keys.keys() - newer_keys.keys()]
    return {
        "introduced": [_vuln_to_dict(v) for v in introduced],
        "fixed": [_vuln_to_dict(v) for v in fixed],
        "introduced_count": len(introduced),
        "fixed_count": len(fixed),
    }


# -- helpers -----------------------------------------------------------


def _scan_to_dict(result: ScanResult) -> dict:
    return {
        "image": result.image,
        "scanner": result.scanner,
        "scanned_at": result.scanned_at.isoformat(),
        "severity_counts": result.severity_counts(),
        "vulnerabilities": [_vuln_to_dict(v) for v in result.vulnerabilities],
        "secrets": [
            {
                "type": s.type,
                "path": s.path,
                "line": s.line,
                "match_preview": s.match_preview,
                "severity": s.severity.display,
            }
            for s in result.secrets
        ],
        "misconfigurations": [
            {
                "rule_id": m.rule_id,
                "title": m.title,
                "severity": m.severity.display,
                "description": m.description,
            }
            for m in result.misconfigurations
        ],
        "packages": [
            {
                "name": p.name,
                "version": p.version,
                "license": p.license,
                "source": p.source,
                "checksum": p.checksum,
            }
            for p in result.packages
        ],
    }


def _vuln_to_dict(v) -> dict:
    return {
        "cve_id": v.cve_id,
        "package": v.package,
        "installed_version": v.installed_version,
        "fixed_version": v.fixed_version,
        "severity": v.severity.display,
        "title": v.title,
        "description": v.description,
        "references": list(v.references),
        "layer": v.layer,
    }


def _sarif_level(severity: Severity) -> str:
    if severity >= Severity.HIGH:
        return "error"
    if severity == Severity.MEDIUM:
        return "warning"
    return "note"


def _security_severity(severity: Severity) -> str:
    mapping = {
        Severity.CRITICAL: "9.0",
        Severity.HIGH: "7.5",
        Severity.MEDIUM: "5.0",
        Severity.LOW: "2.5",
        Severity.UNKNOWN: "0.0",
    }
    return mapping[severity]
