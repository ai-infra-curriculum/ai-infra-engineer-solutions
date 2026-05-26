"""Tests for the distributed-training strategy planner + trainer."""

from pathlib import Path

import pytest

from src.distributed_strategy import (
    HardwareSpec,
    MemoryEstimate,
    ModelSpec,
    Parallelism,
    StrategyConfig,
    estimate_memory,
    estimate_throughput,
    evaluate,
    recommend_strategy,
)
from src.trainer import (
    DistributedTrainer,
    InMemoryBackend,
    TrainerConfig,
    TrainerState,
    make_failing_train_step,
)


def _hw(*, gpus_per_node: int = 8, node_count: int = 4, mem_gb: int = 80) -> HardwareSpec:
    return HardwareSpec(
        gpus_per_node=gpus_per_node, node_count=node_count, gpu_memory_gb=mem_gb,
    )


def _model(*, b: float = 13.0, precision: str = "fp16", checkpointing: bool = False) -> ModelSpec:
    return ModelSpec(
        param_count_billions=b, precision=precision,
        gradient_checkpointing=checkpointing,
    )


class TestModelSpec:
    def test_model_size_for_13b_fp16(self):
        model = _model()
        # 13e9 params × 2 bytes = 26GB.
        assert model.model_size_gb == pytest.approx(26.0)

    def test_optimizer_state_adam_overhead(self):
        model = _model()
        # 13B × 12 bytes/param = 156GB.
        assert model.optimizer_state_gb == pytest.approx(156.0)

    def test_activation_with_checkpointing_halved(self):
        full = _model(checkpointing=False)
        ckpt = _model(checkpointing=True)
        assert ckpt.activation_gb == pytest.approx(full.activation_gb * 0.5)

    def test_precision_options(self):
        fp32 = _model(precision="fp32")
        fp16 = _model(precision="fp16")
        assert fp32.model_size_gb == pytest.approx(fp16.model_size_gb * 2)


class TestMemoryEstimation:
    def test_full_dp_holds_full_model_per_replica(self):
        model = _model(b=7.0)
        config = StrategyConfig(parallelism=Parallelism.DATA_PARALLEL, data_parallel=8)
        mem = estimate_memory(model, config, hardware=_hw())
        assert mem.model_gb == pytest.approx(model.model_size_gb)

    def test_zero3_shards_model_across_dp(self):
        model = _model(b=13.0)
        config = StrategyConfig(parallelism=Parallelism.ZERO_3, data_parallel=32)
        mem = estimate_memory(model, config, hardware=_hw())
        # 13B model × 2 bytes / 32 ranks = ~0.8GB per rank for weights.
        assert mem.model_gb == pytest.approx(26.0 / 32, rel=0.01)

    def test_tensor_parallel_shards_activations(self):
        model = _model(b=13.0)
        full = StrategyConfig(parallelism=Parallelism.DATA_PARALLEL,
                              data_parallel=8)
        tp4 = StrategyConfig(parallelism=Parallelism.TENSOR_PARALLEL,
                             data_parallel=8, tensor_parallel=4)
        mem_full = estimate_memory(model, full, hardware=_hw())
        mem_tp = estimate_memory(model, tp4, hardware=_hw())
        # TP=4 should reduce activation memory ~4x.
        assert mem_tp.activation_gb < mem_full.activation_gb / 3


class TestThroughputEstimation:
    def test_throughput_scales_with_gpus(self):
        model = _model(b=7.0)
        small = StrategyConfig(parallelism=Parallelism.DATA_PARALLEL,
                                data_parallel=8)
        large = StrategyConfig(parallelism=Parallelism.DATA_PARALLEL,
                                data_parallel=32)
        small_tp = estimate_throughput(model, small, hardware=_hw())
        large_tp = estimate_throughput(model, large, hardware=_hw())
        assert large_tp.samples_per_second > small_tp.samples_per_second

    def test_tp_across_nodes_penalized(self):
        # TP=16 spans multiple 8-GPU nodes; should reduce efficiency.
        model = _model(b=13.0)
        tp16 = StrategyConfig(parallelism=Parallelism.TENSOR_PARALLEL,
                              data_parallel=2, tensor_parallel=16)
        tp8 = StrategyConfig(parallelism=Parallelism.TENSOR_PARALLEL,
                              data_parallel=4, tensor_parallel=8)
        hw = _hw()
        eff_16 = estimate_throughput(model, tp16, hardware=hw).scaling_efficiency_percent
        eff_8 = estimate_throughput(model, tp8, hardware=hw).scaling_efficiency_percent
        assert eff_16 < eff_8

    def test_pipeline_bubble_overhead(self):
        model = _model(b=7.0)
        pp4 = StrategyConfig(parallelism=Parallelism.PIPELINE_PARALLEL,
                              data_parallel=8, pipeline_parallel=4)
        ddp = StrategyConfig(parallelism=Parallelism.DATA_PARALLEL,
                              data_parallel=32)
        hw = _hw()
        eff_pp = estimate_throughput(model, pp4, hardware=hw).scaling_efficiency_percent
        eff_ddp = estimate_throughput(model, ddp, hardware=hw).scaling_efficiency_percent
        assert eff_pp < eff_ddp


class TestStrategyRecommender:
    def test_small_model_chooses_ddp_or_zero(self):
        model = _model(b=1.0)
        result = recommend_strategy(model, _hw())
        assert result.best.feasible
        # 1B model is small enough for any strategy; expect a
        # DP-family choice (DDP / ZeRO-*).
        assert result.best.config.parallelism in {
            Parallelism.DATA_PARALLEL, Parallelism.ZERO_1,
            Parallelism.ZERO_2, Parallelism.ZERO_3, Parallelism.FSDP,
        }

    def test_huge_model_requires_sharding(self):
        # 70B model — DP alone is hopeless (140GB > 80GB).
        model = _model(b=70.0)
        result = recommend_strategy(model, _hw())
        if result.best.feasible:
            # The recommendation must shard the model (TP, PP, or ZeRO-3/FSDP).
            shards = {
                Parallelism.TENSOR_PARALLEL, Parallelism.PIPELINE_PARALLEL,
                Parallelism.ZERO_3, Parallelism.FSDP,
            }
            assert result.best.config.parallelism in shards

    def test_infeasible_when_cluster_too_small(self):
        model = _model(b=70.0)
        # Tiny cluster — 1 GPU with 80GB.
        result = recommend_strategy(model, _hw(gpus_per_node=1, node_count=1))
        assert not result.best.feasible
        assert "exceeds device capacity" in (
            " ".join(result.best.notes) or result.rationale
        )

    def test_evaluation_includes_per_gpu_memory(self):
        model = _model(b=7.0)
        config = StrategyConfig(parallelism=Parallelism.ZERO_2, data_parallel=8)
        eval_result = evaluate(model, config, hardware=_hw())
        assert eval_result.memory_per_gpu.total_gb > 0
        assert eval_result.throughput.samples_per_second > 0

    def test_strategy_exceeding_cluster_size_infeasible(self):
        model = _model(b=1.0)
        config = StrategyConfig(parallelism=Parallelism.DATA_PARALLEL,
                                 data_parallel=100)
        eval_result = evaluate(model, config, hardware=_hw())
        assert not eval_result.feasible


class TestDistributedTrainer:
    def _make_trainer(
        self,
        *,
        steps: int = 30,
        checkpoint_every: int = 10,
        fail_step: int | None = None,
        fail_count: int = 1,
        enable_recovery: bool = True,
    ) -> DistributedTrainer:
        model = _model(b=7.0)
        hardware = _hw(node_count=2)
        strategy = StrategyConfig(
            parallelism=Parallelism.ZERO_2, data_parallel=hardware.total_gpus,
        )
        backend = InMemoryBackend(rank=0, world_size=hardware.total_gpus)
        train_step = (
            make_failing_train_step(fail_at_step=fail_step, fail_count=fail_count)
            if fail_step is not None else None
        )
        return DistributedTrainer(
            backend=backend,
            model=model,
            strategy=strategy,
            hardware=hardware,
            config=TrainerConfig(
                total_steps=steps,
                log_every=10,
                checkpoint_every=checkpoint_every,
                enable_fault_recovery=enable_recovery,
            ),
            train_step_fn=train_step,
        )

    def test_full_run_completes(self):
        trainer = self._make_trainer(steps=30, checkpoint_every=10)
        report = trainer.train()
        assert report.state is TrainerState.COMPLETED
        assert report.steps_completed == 30
        assert len(report.checkpoints) >= 2

    def test_checkpoints_taken_at_interval(self):
        trainer = self._make_trainer(steps=100, checkpoint_every=25)
        report = trainer.train()
        assert len(report.checkpoints) == 4  # steps 25, 50, 75, 100

    def test_failure_triggers_recovery(self):
        trainer = self._make_trainer(
            steps=40, checkpoint_every=10, fail_step=25, fail_count=1,
        )
        report = trainer.train()
        # Should recover and complete.
        assert report.state is TrainerState.COMPLETED
        assert report.recoveries == 1

    def test_max_recovery_attempts_exceeded(self):
        trainer = self._make_trainer(
            steps=40, checkpoint_every=10, fail_step=10, fail_count=99,
        )
        # Restrict retries to 2 by editing the config in place.
        trainer.config.max_recovery_attempts = 2
        report = trainer.train()
        assert report.state is TrainerState.FAILED
        assert report.recoveries > 0
        assert "max recovery" in (report.failure_reason or "").lower()

    def test_metrics_history_grows_each_step(self):
        trainer = self._make_trainer(steps=20, checkpoint_every=10)
        report = trainer.train()
        assert len(report.metrics_history) == 20

    def test_loss_decreases_over_steps(self):
        trainer = self._make_trainer(steps=50, checkpoint_every=10)
        report = trainer.train()
        first = report.metrics_history[0].train_loss
        last = report.metrics_history[-1].train_loss
        assert last < first

    def test_infeasible_strategy_returns_failed(self):
        # Build a strategy that demands more GPUs than the cluster has.
        model = _model(b=70.0)
        hardware = _hw(gpus_per_node=1, node_count=1)
        strategy = StrategyConfig(
            parallelism=Parallelism.DATA_PARALLEL,
            data_parallel=hardware.total_gpus,
        )
        backend = InMemoryBackend(rank=0, world_size=hardware.total_gpus)
        trainer = DistributedTrainer(
            backend=backend, model=model, strategy=strategy,
            hardware=hardware, config=TrainerConfig(total_steps=5),
        )
        report = trainer.train()
        assert report.state is TrainerState.FAILED
        assert "memory" in (report.failure_reason or "").lower()


class TestBackend:
    def test_all_reduce_sum(self):
        backend = InMemoryBackend(rank=0, world_size=4)
        result = backend.all_reduce(2.0, op="sum")
        assert result == 8.0

    def test_all_reduce_mean(self):
        backend = InMemoryBackend(rank=0, world_size=4)
        result = backend.all_reduce(2.0, op="mean")
        assert result == 2.0

    def test_unknown_op_raises(self):
        backend = InMemoryBackend(rank=0, world_size=2)
        with pytest.raises(ValueError):
            backend.all_reduce(1.0, op="xor")
