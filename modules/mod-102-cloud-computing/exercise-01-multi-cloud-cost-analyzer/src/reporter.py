"""
Report Generation

Emit comparison + optimization results in multiple formats: JSON for
downstream tooling, CSV for spreadsheets, and a minimal self-contained
HTML report for sharing. The reporter is deliberately framework-light
so it has no third-party rendering dependencies.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from .cost_comparator import ComparisonResult
from .optimizer import Recommendation


def _json_default(obj: Any) -> Any:
    """JSON serialization fallback for dataclasses, enums, and datetimes."""
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_json(
    comparison: ComparisonResult,
    recommendations: Optional[List[Recommendation]] = None,
    indent: int = 2,
) -> str:
    """Render the report as JSON."""
    payload = {
        "generated_at": datetime.now().isoformat(),
        "comparison": comparison,
        "recommendations": recommendations or [],
    }
    return json.dumps(payload, default=_json_default, indent=indent)


def to_csv(comparison: ComparisonResult) -> str:
    """Render the per-provider quote table as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "provider",
        "instance_type",
        "pricing_model",
        "compute_monthly_usd",
        "storage_monthly_usd",
        "egress_monthly_usd",
        "total_monthly_usd",
        "notes",
    ])
    for quote in comparison.quotes:
        compute = round(
            quote.instance_pricing.price_per_hour * comparison.workload.hours_per_month, 2,
        )
        writer.writerow([
            quote.provider,
            quote.instance_pricing.instance_spec.instance_type,
            quote.instance_pricing.pricing_model.value,
            compute,
            quote.storage_monthly_cost,
            quote.egress_monthly_cost,
            quote.total_monthly_cost,
            "; ".join(quote.notes),
        ])
    return buf.getvalue()


def to_html(
    comparison: ComparisonResult,
    recommendations: Optional[List[Recommendation]] = None,
) -> str:
    """Render a minimal self-contained HTML report."""
    rec_list = recommendations or []
    rows = ""
    for quote in comparison.quotes:
        compute = round(
            quote.instance_pricing.price_per_hour * comparison.workload.hours_per_month, 2,
        )
        rows += (
            "<tr>"
            f"<td>{quote.provider}</td>"
            f"<td>{quote.instance_pricing.instance_spec.instance_type}</td>"
            f"<td>{quote.instance_pricing.pricing_model.value}</td>"
            f"<td>${compute:,.2f}</td>"
            f"<td>${quote.storage_monthly_cost:,.2f}</td>"
            f"<td>${quote.egress_monthly_cost:,.2f}</td>"
            f"<td><strong>${quote.total_monthly_cost:,.2f}</strong></td>"
            "</tr>"
        )
    rec_rows = ""
    for rec in rec_list:
        rec_rows += (
            "<tr>"
            f"<td>{rec.title}</td>"
            f"<td>${rec.estimated_monthly_savings_usd:,.2f}</td>"
            f"<td>{rec.confidence.value}</td>"
            f"<td>{rec.action}</td>"
            "</tr>"
        )
    return (
        "<!doctype html>\n"
        "<html><head><meta charset=\"utf-8\">"
        "<title>Cloud Cost Analyzer Report</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;margin:2rem;max-width:1000px;}"
        "h1,h2{color:#222;}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0;}"
        "th,td{padding:0.5rem 0.75rem;border-bottom:1px solid #ddd;text-align:left;}"
        "th{background:#f4f4f4;}"
        "tr:hover{background:#fafafa;}"
        ".summary{background:#f7f9fc;padding:1rem;border-left:4px solid #2b7;}"
        "</style></head><body>"
        "<h1>Multi-Cloud Cost Comparison</h1>"
        f"<p>Generated at {datetime.now().isoformat(timespec='seconds')}</p>"
        f"<div class=\"summary\">"
        f"<strong>Cheapest:</strong> {comparison.cheapest_provider}"
        f" &middot; <strong>Most expensive:</strong> {comparison.most_expensive_provider}"
        f" &middot; <strong>Spread:</strong> {comparison.spread_percent}%"
        f"</div>"
        "<h2>Per-Provider Quotes</h2>"
        "<table><thead><tr>"
        "<th>Provider</th><th>Instance</th><th>Model</th>"
        "<th>Compute/mo</th><th>Storage/mo</th><th>Egress/mo</th><th>Total/mo</th>"
        "</tr></thead><tbody>"
        f"{rows}"
        "</tbody></table>"
        + (
            "<h2>Optimization Recommendations</h2>"
            "<table><thead><tr>"
            "<th>Recommendation</th><th>Est. Monthly Savings</th>"
            "<th>Confidence</th><th>Action</th>"
            "</tr></thead><tbody>"
            f"{rec_rows}"
            "</tbody></table>"
            if rec_list
            else ""
        )
        + "</body></html>"
    )
