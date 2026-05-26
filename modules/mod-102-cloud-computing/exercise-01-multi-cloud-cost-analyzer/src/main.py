"""
Multi-Cloud Cost Analyzer - CLI Entry Point

Compare costs and produce optimization recommendations across AWS, GCP,
and Azure. Uses static price catalogs by default so the tool runs without
cloud credentials; pass real boto3 / google-cloud / azure clients to the
provider constructors to enable live API queries.

Subcommands:
    compare         Cross-provider compute + storage + egress quote.
    optimize        Optimization recommendations for a given instance.
    storage         Side-by-side storage pricing.
    validate        Sanity checks on the static catalog wiring.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Optional

import click

from .cloud_providers.aws import AWSProvider
from .cloud_providers.azure import AzureProvider
from .cloud_providers.base import (
    CloudProvider,
    InstanceFamily,
    InstanceSpec,
    PricingModel,
)
from .cloud_providers.gcp import GCPProvider
from .cost_comparator import CostComparator, WorkloadSpec
from .optimizer import CostOptimizer, UsageProfile
from .reporter import to_csv, to_html, to_json


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _build_providers(
    aws_region: str,
    gcp_region: str,
    azure_region: str,
) -> Dict[str, CloudProvider]:
    return {
        "aws": AWSProvider(region=aws_region),
        "gcp": GCPProvider(region=gcp_region),
        "azure": AzureProvider(region=azure_region),
    }


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """Multi-Cloud Cost Analyzer."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--provider", default="aws", type=click.Choice(["aws", "gcp", "azure"]))
@click.option("--instance", required=True, help="Reference instance type (in --provider's catalog)")
@click.option("--hours-per-month", default=730.0, type=float)
@click.option("--storage-gb", default=0.0, type=float)
@click.option("--storage-class", default="STANDARD")
@click.option("--egress-gb", default=0.0, type=float)
@click.option("--pricing-model", default="on_demand", type=click.Choice([m.value for m in PricingModel]))
@click.option("--format", "fmt", default="text", type=click.Choice(["text", "json", "csv", "html"]))
@click.option("--output", type=click.Path(dir_okay=False), help="Write report to file")
@click.option("--aws-region", default="us-east-1")
@click.option("--gcp-region", default="us-central1")
@click.option("--azure-region", default="eastus")
def compare(
    provider: str,
    instance: str,
    hours_per_month: float,
    storage_gb: float,
    storage_class: str,
    egress_gb: float,
    pricing_model: str,
    fmt: str,
    output: Optional[str],
    aws_region: str,
    gcp_region: str,
    azure_region: str,
) -> None:
    """Compare a workload across all three clouds."""
    providers = _build_providers(aws_region, gcp_region, azure_region)
    reference_provider = providers[provider]
    pricing_info = reference_provider.get_instance_pricing(instance, PricingModel(pricing_model))
    reference_spec = pricing_info.instance_spec

    workload = WorkloadSpec(
        reference_instance=reference_spec,
        storage_gb=storage_gb,
        storage_class=storage_class,
        monthly_egress_gb=egress_gb,
        pricing_model=PricingModel(pricing_model),
        hours_per_month=hours_per_month,
    )
    comparator = CostComparator(providers)
    result = comparator.compare(workload)

    if fmt == "json":
        body = to_json(result)
    elif fmt == "csv":
        body = to_csv(result)
    elif fmt == "html":
        body = to_html(result)
    else:
        body = _format_text(result)

    if output:
        Path(output).write_text(body)
        click.echo(f"Report written to {output}")
    else:
        click.echo(body)


@cli.command()
@click.option("--provider", default="aws", type=click.Choice(["aws", "gcp", "azure"]))
@click.option("--instance", required=True)
@click.option("--avg-cpu", default=50.0, type=float)
@click.option("--avg-memory", default=50.0, type=float)
@click.option("--avg-gpu", default=0.0, type=float)
@click.option("--monthly-hours", default=730.0, type=float)
@click.option("--interruption-tolerant/--not-tolerant", default=False)
@click.option("--age-days", default=30, type=int)
@click.option("--current-pricing-model", default="on_demand", type=click.Choice([m.value for m in PricingModel]))
def optimize(
    provider: str,
    instance: str,
    avg_cpu: float,
    avg_memory: float,
    avg_gpu: float,
    monthly_hours: float,
    interruption_tolerant: bool,
    age_days: int,
    current_pricing_model: str,
) -> None:
    """Produce optimization recommendations for a deployment."""
    providers = _build_providers("us-east-1", "us-central1", "eastus")
    cloud = providers[provider]
    pricing = cloud.get_instance_pricing(instance, PricingModel(current_pricing_model))
    optimizer = CostOptimizer(cloud)
    usage = UsageProfile(
        avg_cpu_percent=avg_cpu,
        avg_memory_percent=avg_memory,
        avg_gpu_percent=avg_gpu,
        monthly_hours=monthly_hours,
        interruption_tolerant=interruption_tolerant,
        age_days=age_days,
    )
    recs = optimizer.recommend(pricing.instance_spec, usage, PricingModel(current_pricing_model))

    if not recs:
        click.echo("No optimization recommendations.")
        return
    for rec in recs:
        click.echo(
            f"[{rec.confidence.value.upper()}] {rec.title}\n"
            f"  Savings: ${rec.estimated_monthly_savings_usd:,.2f}/month\n"
            f"  Action:  {rec.action}\n"
        )


@cli.command()
@click.option("--size-gb", default=1000.0, type=float)
def storage(size_gb: float) -> None:
    """Compare storage costs across providers."""
    providers = _build_providers("us-east-1", "us-central1", "eastus")
    comparator = CostComparator(providers)
    rows = comparator.compare_storage(size_gb)
    for provider_name, info in sorted(rows.items(), key=lambda kv: kv[1]["monthly_cost"]):
        click.echo(
            f"{provider_name:6s} {info['storage_class']:20s} "
            f"${info['monthly_cost']:,.2f}/month "
            f"(@ ${info['price_per_gb_month']:.4f}/GB-month)"
        )


@cli.command()
def validate() -> None:
    """Sanity check: pull pricing for one instance from each provider."""
    providers = _build_providers("us-east-1", "us-central1", "eastus")
    samples = {"aws": "m5.large", "gcp": "n2-standard-2", "azure": "Standard_D2s_v5"}
    failed = []
    for name, instance in samples.items():
        try:
            info = providers[name].get_instance_pricing(instance, PricingModel.ON_DEMAND)
            click.echo(f"OK   {name} {instance}: ${info.price_per_hour:.4f}/hour")
        except Exception as exc:  # pragma: no cover - defensive
            click.echo(f"FAIL {name} {instance}: {exc}", err=True)
            failed.append(name)
    if failed:
        sys.exit(1)


def _format_text(result) -> str:
    lines = [
        "Multi-Cloud Cost Comparison",
        "===========================",
        f"Cheapest:       {result.cheapest_provider}",
        f"Most expensive: {result.most_expensive_provider}",
        f"Spread:         {result.spread_percent}%",
        "",
        f"{'Provider':<8} {'Instance':<26} {'Model':<14} {'Total/month':>14}",
    ]
    for quote in result.quotes:
        lines.append(
            f"{quote.provider:<8} "
            f"{quote.instance_pricing.instance_spec.instance_type:<26} "
            f"{quote.instance_pricing.pricing_model.value:<14} "
            f"${quote.total_monthly_cost:>13,.2f}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    cli()
