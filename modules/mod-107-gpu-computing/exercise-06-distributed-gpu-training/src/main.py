"""
Distributed Training — CLI

Subcommands:
    plan        Compare distributed-training strategies for a given
                (model_size, cluster) and print the recommended config.
    train       Run a synthetic distributed training loop end-to-end.
    fault-drill Run the same loop with a forced failure to exercise
                fault recovery + checkpoint restoration.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .distributed_strategy import (
    HardwareSpec,
    ModelSpec,
    Parallelism,
    StrategyConfig,
    evaluate,
    recommend_strategy,
)
from .trainer import (
    DistributedTrainer,
    InMemoryBackend,
    TrainerConfig,
    make_failing_train_step,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Distributed training framework."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--param-count-billions", default=13.0, type=float)
@click.option("--precision", default="fp16",
              type=click.Choice(["fp32", "fp16", "bf16", "fp8"]))
@click.option("--gpus-per-node", default=8, type=int)
@click.option("--node-count", default=4, type=int)
@click.option("--gpu-memory-gb", default=80, type=int)
@click.option("--micro-batch-size", default=8, type=int)
@click.option("--gradient-checkpointing/--no-gradient-checkpointing", default=False)
def plan(
    param_count_billions: float,
    precision: str,
    gpus_per_node: int,
    node_count: int,
    gpu_memory_gb: int,
    micro_batch_size: int,
    gradient_checkpointing: bool,
) -> None:
    """Pick a distributed-training strategy for the given model + cluster."""
    model = ModelSpec(
        param_count_billions=param_count_billions,
        precision=precision,
        micro_batch_size=micro_batch_size,
        gradient_checkpointing=gradient_checkpointing,
    )
    hardware = HardwareSpec(
        gpus_per_node=gpus_per_node, node_count=node_count,
        gpu_memory_gb=gpu_memory_gb,
    )
    result = recommend_strategy(model, hardware)
    click.echo(f"Model: {model.param_count_billions:.1f}B params ({precision})")
    click.echo(f"  model size: {model.model_size_gb:.1f}GB")
    click.echo(f"  optimizer state: {model.optimizer_state_gb:.1f}GB")
    click.echo(f"  activations: {model.activation_gb:.1f}GB")
    click.echo(f"Cluster: {hardware.total_gpus} GPUs across {hardware.node_count} nodes")
    click.echo(f"\n=> {result.rationale}\n")
    click.echo("Top candidates:")
    for cand in result.candidates[:5]:
        marker = "✓" if cand.feasible else "✗"
        click.echo(
            f"  {marker} {cand.config.parallelism.value:<18s} "
            f"DP={cand.config.data_parallel:<2d} "
            f"TP={cand.config.tensor_parallel:<2d} "
            f"PP={cand.config.pipeline_parallel:<2d}  "
            f"per-gpu={cand.memory_per_gpu.total_gb:>6.1f}GB  "
            f"sps={cand.throughput.samples_per_second:>7.1f}  "
            f"eff={cand.throughput.scaling_efficiency_percent:>5.1f}%"
        )


@cli.command()
@click.option("--steps", default=100, type=int)
@click.option("--checkpoint-every", default=25, type=int)
@click.option("--log-every", default=20, type=int)
def train(steps: int, checkpoint_every: int, log_every: int) -> None:
    """Run a synthetic distributed training loop."""
    model = ModelSpec(param_count_billions=7.0)
    hardware = HardwareSpec(gpus_per_node=8, node_count=2)
    strategy = StrategyConfig(
        parallelism=Parallelism.ZERO_2,
        data_parallel=hardware.total_gpus,
    )
    backend = InMemoryBackend(rank=0, world_size=hardware.total_gpus)
    trainer = DistributedTrainer(
        backend=backend,
        model=model,
        strategy=strategy,
        hardware=hardware,
        config=TrainerConfig(
            total_steps=steps,
            log_every=log_every,
            checkpoint_every=checkpoint_every,
        ),
    )
    report = trainer.train()
    click.echo(f"State: {report.state.value}")
    click.echo(f"Steps: {report.steps_completed}")
    click.echo(f"Checkpoints: {len(report.checkpoints)}")
    click.echo(f"Recoveries: {report.recoveries}")
    if report.metrics_history:
        last = report.metrics_history[-1]
        click.echo(
            f"Final loss: {last.train_loss:.4f}  "
            f"sps={last.samples_per_second:.1f}  "
            f"grad_norm={last.grad_norm:.4f}"
        )


@cli.command()
@click.option("--steps", default=80, type=int)
@click.option("--fail-at-step", default=30, type=int)
@click.option("--checkpoint-every", default=10, type=int)
def fault_drill(steps: int, fail_at_step: int, checkpoint_every: int) -> None:
    """Force a failure mid-training to demonstrate recovery."""
    model = ModelSpec(param_count_billions=7.0)
    hardware = HardwareSpec(gpus_per_node=8, node_count=2)
    strategy = StrategyConfig(
        parallelism=Parallelism.ZERO_2,
        data_parallel=hardware.total_gpus,
    )
    backend = InMemoryBackend(rank=0, world_size=hardware.total_gpus)
    trainer = DistributedTrainer(
        backend=backend,
        model=model,
        strategy=strategy,
        hardware=hardware,
        config=TrainerConfig(
            total_steps=steps,
            log_every=10,
            checkpoint_every=checkpoint_every,
            enable_fault_recovery=True,
        ),
        train_step_fn=make_failing_train_step(fail_at_step=fail_at_step, fail_count=1),
    )
    report = trainer.train()
    click.echo(f"State: {report.state.value}")
    click.echo(f"Steps: {report.steps_completed} (of {steps})")
    click.echo(f"Checkpoints: {len(report.checkpoints)}")
    click.echo(f"Recoveries: {report.recoveries}")


if __name__ == "__main__":
    cli()
