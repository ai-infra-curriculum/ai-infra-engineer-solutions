"""gpu-info CLI."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict

import click

from . import bench, inventory


# Theoretical peak fp32 TFLOPS per chip (approximate)
PEAK_TFLOPS = {
    "H100": 67, "A100": 19.5, "V100": 15.7,
    "RTX 4090": 82.6, "RTX 3090": 35.6, "RTX 3080": 29.8,
    "L4": 30.3, "L40S": 91.6, "T4": 8.1,
    "A10": 31.2, "A30": 10.3,
}


def _peak_for(name: str) -> float | None:
    for key, val in PEAK_TFLOPS.items():
        if key in name:
            return val
    return None


@click.command()
@click.option("--json", "as_json", is_flag=True)
@click.option("--no-bench", is_flag=True)
def cli(as_json: bool, no_bench: bool) -> None:
    """Inventory GPUs + run benchmarks; exit 0 healthy, 1 degraded, 2 no GPU."""
    try:
        gpus = inventory.inventory()
    except Exception as e:
        click.echo(f"NVML init failed: {e}", err=True)
        sys.exit(2)

    if not gpus:
        click.echo("no GPUs detected", err=True)
        sys.exit(2)

    report: dict = {"gpus": [], "topology": {}}
    degraded = False

    for g in gpus:
        entry = asdict(g)
        if not no_bench:
            try:
                tflops = bench.matmul_tflops(g.index)
                bw = bench.bandwidth_gbs(g.index)
                entry["measured_tflops"] = round(tflops, 2)
                entry["bandwidth_gbs"] = round(bw, 2)
                peak = _peak_for(g.name)
                if peak:
                    entry["peak_tflops"] = peak
                    entry["pct_of_peak"] = round(tflops / peak * 100, 1)
                    if tflops < peak * 0.5:
                        entry["warning"] = "measured TFLOPS < 50% of peak"
                        degraded = True
            except Exception as e:
                entry["bench_error"] = str(e)
                degraded = True
        report["gpus"].append(entry)

    try:
        topo = inventory.nvlink_topology()
        report["topology"] = {f"{i}-{j}": kind for (i, j), kind in topo.items()}
    except Exception:
        pass

    if as_json:
        click.echo(json.dumps(report, indent=2))
    else:
        for g in report["gpus"]:
            click.echo(f"[{g['index']}] {g['name']}")
            click.echo(f"  compute {g['compute_capability']}, {g['total_mem_gb']:.1f} GB total, {g['free_mem_gb']:.1f} GB free")
            if "measured_tflops" in g:
                pct = g.get("pct_of_peak")
                click.echo(f"  matmul: {g['measured_tflops']} TFLOPS" +
                            (f" ({pct}% of peak)" if pct else ""))
                click.echo(f"  bandwidth: {g['bandwidth_gbs']} GB/s")
            if "warning" in g:
                click.echo(f"  ⚠ {g['warning']}")
        for pair, kind in report["topology"].items():
            click.echo(f"link {pair}: {kind}")

    sys.exit(1 if degraded else 0)


if __name__ == "__main__":
    cli()
