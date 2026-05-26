"""Tests for the GPU profiler + optimizer."""

import pytest

from src.optimizer import (
    Confidence,
    OptimizationTechnique,
    PerformanceOptimizer,
    detect_regression,
)
from src.profiler import (
    BottleneckAnalyzer,
    SyntheticTraceProfile,
    SyntheticTraceSource,
    TraceCategory,
    TraceEvent,
)


def _collect(profile: SyntheticTraceProfile, *, steps: int = 30, batch: int = 32):
    run = SyntheticTraceSource(profile).collect(steps=steps, batch_size=batch)
    return run


class TestBottleneckAnalyzer:
    def test_balanced_profile_compute_dominant(self):
        run = _collect(SyntheticTraceProfile())
        report = BottleneckAnalyzer().analyze(run)
        assert report.primary_bottleneck is TraceCategory.BACKWARD
        assert report.is_compute_bound()

    def test_data_loader_bound(self):
        profile = SyntheticTraceProfile(
            data_loading_ms=300.0, h2d_copy_ms=2.0,
            forward_ms=40.0, backward_ms=60.0, optimizer_ms=10.0,
        )
        report = BottleneckAnalyzer().analyze(_collect(profile))
        assert report.is_data_loader_bound()
        assert report.data_loading_percent > 60.0

    def test_memory_movement_bound(self):
        profile = SyntheticTraceProfile(
            data_loading_ms=20.0, h2d_copy_ms=120.0,
            forward_ms=40.0, backward_ms=60.0, optimizer_ms=5.0,
        )
        report = BottleneckAnalyzer().analyze(_collect(profile))
        assert report.is_memory_movement_bound()

    def test_collective_bound(self):
        profile = SyntheticTraceProfile(
            data_loading_ms=15.0, h2d_copy_ms=5.0,
            forward_ms=50.0, backward_ms=70.0, optimizer_ms=10.0,
            collective_ms=200.0, device_count=4,
        )
        report = BottleneckAnalyzer().analyze(
            _collect(profile), single_device_throughput=300.0,
        )
        assert report.is_collective_bound()
        assert report.multi_gpu_scaling_efficiency_percent is not None
        assert report.multi_gpu_scaling_efficiency_percent < 50.0

    def test_breakdown_sums_to_100(self):
        report = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile()))
        total = sum(b.percent for b in report.breakdown)
        assert total == pytest.approx(100.0, abs=0.5)

    def test_throughput_calculation(self):
        # Each step processes 32 samples; total step ms ≈ 288ms (default profile).
        report = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile(), steps=10, batch=32))
        # Throughput = total_samples / total_seconds.
        # With 10 steps × 32 samples = 320 samples, total ms = 288 × 10 = 2880 → 2.88s.
        # Throughput ≈ 111 samples/sec.
        assert 100.0 < report.avg_throughput_samples_per_sec < 130.0

    def test_memory_utilization_percent(self):
        profile = SyntheticTraceProfile(allocated_gb=30.0, capacity_gb=40.0)
        report = BottleneckAnalyzer().analyze(_collect(profile))
        assert report.avg_gpu_memory_utilization_percent == pytest.approx(75.0)

    def test_empty_run_raises(self):
        from src.profiler import ProfileRun
        with pytest.raises(ValueError):
            BottleneckAnalyzer().analyze(ProfileRun(name="empty", steps=[], device_count=1))


class TestPerformanceOptimizer:
    def test_recommends_mixed_precision_for_compute_bound(self):
        profile = SyntheticTraceProfile(
            forward_ms=200.0, backward_ms=300.0,
            data_loading_ms=10.0, h2d_copy_ms=5.0, optimizer_ms=10.0,
        )
        report = BottleneckAnalyzer().analyze(_collect(profile))
        plan = PerformanceOptimizer().recommend(report)
        techniques = {r.technique for r in plan.recommendations}
        assert OptimizationTechnique.MIXED_PRECISION in techniques

    def test_recommends_data_workers_for_data_loader_bound(self):
        profile = SyntheticTraceProfile(
            data_loading_ms=300.0, forward_ms=40.0, backward_ms=60.0,
        )
        report = BottleneckAnalyzer().analyze(_collect(profile))
        plan = PerformanceOptimizer().recommend(report)
        techniques = {r.technique for r in plan.recommendations}
        assert OptimizationTechnique.INCREASE_DATA_WORKERS in techniques
        assert OptimizationTechnique.PREFETCH_PIPELINE in techniques

    def test_recommends_pinned_memory_for_memory_movement(self):
        profile = SyntheticTraceProfile(
            data_loading_ms=20.0, h2d_copy_ms=100.0,
            forward_ms=40.0, backward_ms=60.0, optimizer_ms=10.0,
        )
        report = BottleneckAnalyzer().analyze(_collect(profile))
        plan = PerformanceOptimizer().recommend(report)
        assert any(
            r.technique is OptimizationTechnique.PINNED_MEMORY
            for r in plan.recommendations
        )

    def test_recommends_larger_batch_for_underutilized_memory(self):
        profile = SyntheticTraceProfile(allocated_gb=4.0, capacity_gb=40.0)
        report = BottleneckAnalyzer().analyze(_collect(profile))
        plan = PerformanceOptimizer().recommend(report)
        techniques = {r.technique for r in plan.recommendations}
        assert OptimizationTechnique.INCREASE_BATCH_SIZE in techniques

    def test_recommends_gradient_checkpointing_for_memory_pressure(self):
        profile = SyntheticTraceProfile(allocated_gb=38.0, capacity_gb=40.0)
        report = BottleneckAnalyzer().analyze(_collect(profile))
        plan = PerformanceOptimizer().recommend(report)
        techniques = {r.technique for r in plan.recommendations}
        assert OptimizationTechnique.GRADIENT_CHECKPOINTING in techniques

    def test_recommends_overlap_for_collective_bound(self):
        profile = SyntheticTraceProfile(
            collective_ms=120.0, device_count=4,
            data_loading_ms=15.0, forward_ms=50.0, backward_ms=70.0,
        )
        report = BottleneckAnalyzer().analyze(
            _collect(profile), single_device_throughput=200.0,
        )
        plan = PerformanceOptimizer().recommend(report)
        techniques = {r.technique for r in plan.recommendations}
        assert OptimizationTechnique.OVERLAP_COMPUTE_COMMS in techniques
        assert OptimizationTechnique.NCCL_TUNING in techniques

    def test_recommendations_ranked_by_speedup(self):
        report = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile()))
        plan = PerformanceOptimizer().recommend(report)
        speedups = [r.estimated_speedup for r in plan.recommendations]
        assert speedups == sorted(speedups, reverse=True)

    def test_dedup_by_technique(self):
        # Memory-pressure + compute-bound both generate
        # OVERLAP_COMPUTE_COMMS only via collective rec; test that the
        # collective + scaling efficiency recs dedup to one entry.
        profile = SyntheticTraceProfile(
            collective_ms=150.0, device_count=8,
            data_loading_ms=15.0, forward_ms=50.0, backward_ms=70.0,
        )
        report = BottleneckAnalyzer().analyze(
            _collect(profile), single_device_throughput=200.0,
        )
        plan = PerformanceOptimizer().recommend(report)
        techniques = [r.technique for r in plan.recommendations]
        assert len(techniques) == len(set(techniques))

    def test_aggregate_speedup_is_geometric(self):
        report = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile()))
        plan = PerformanceOptimizer().recommend(report)
        expected = 1.0
        for r in plan.recommendations:
            expected *= r.estimated_speedup
        assert plan.expected_aggregate_speedup == pytest.approx(round(expected, 3), abs=0.01)


class TestRegressionDetection:
    def test_no_regression_on_improvement(self):
        baseline = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile(
            data_loading_ms=300.0, forward_ms=50.0, backward_ms=60.0,
        )))
        candidate = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile()))
        result = detect_regression(baseline, candidate)
        assert not result.regressed
        assert result.delta_percent > 0

    def test_regression_on_slowdown(self):
        baseline = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile()))
        candidate = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile(
            data_loading_ms=300.0, forward_ms=200.0, backward_ms=300.0,
        )))
        result = detect_regression(baseline, candidate)
        assert result.regressed
        assert result.delta_percent < -5.0

    def test_threshold_respected(self):
        baseline = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile()))
        # Same scenario → ~0% delta; should not regress under any
        # non-zero threshold.
        candidate = BottleneckAnalyzer().analyze(_collect(SyntheticTraceProfile()))
        result = detect_regression(baseline, candidate, threshold_percent=1.0)
        assert not result.regressed

    def test_baseline_zero_no_regression(self):
        # Edge case: an empty/zero baseline doesn't crash.
        from src.profiler import BottleneckReport
        zero = BottleneckReport(
            primary_bottleneck=TraceCategory.IDLE, breakdown=[],
            gpu_compute_percent=0.0, data_loading_percent=0.0,
            memory_movement_percent=0.0, collective_percent=0.0,
            idle_percent=100.0, avg_throughput_samples_per_sec=0.0,
            avg_gpu_memory_utilization_percent=0.0,
            multi_gpu_scaling_efficiency_percent=None,
        )
        result = detect_regression(zero, zero)
        assert not result.regressed
