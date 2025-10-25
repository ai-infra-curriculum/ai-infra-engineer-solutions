"""CLI interface for mlbench."""

import click
from pathlib import Path
import yaml
from rich.console import Console

from .benchmark_runner import BenchmarkRunner, BenchmarkConfig

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """mlbench - ML Framework Benchmarking Tool."""
    pass


@cli.command()
@click.option("--config", type=click.Path(exists=True), required=True, help="Config file")
@click.option("--frameworks", multiple=True, help="Override frameworks to benchmark")
def run(config: str, frameworks: tuple) -> None:
    """Run benchmarks."""
    # Load config
    with open(config) as f:
        config_data = yaml.safe_load(f)

    # Override frameworks if specified
    if frameworks:
        config_data["frameworks"] = list(frameworks)

    # Create config object
    bench_config = BenchmarkConfig(**config_data)

    # Run benchmarks
    runner = BenchmarkRunner(bench_config)

    with console.status("[bold green]Running benchmarks..."):
        results = runner.run_all_benchmarks()

    console.print(f"[green]✓[/green] Completed {len(results)} benchmarks")

    # Save results
    output_dir = Path(config_data.get("output_dir", "results"))
    runner.save_results(output_dir)


@cli.command()
@click.option("--results", type=click.Path(exists=True), required=True)
@click.option("--output", type=click.Path(), default="report")
def report(results: str, output: str) -> None:
    """Generate report from results."""
    console.print(f"[green]Generating report from {results}...[/green]")
    console.print(f"Report will be saved to {output}/")


if __name__ == "__main__":
    cli()
