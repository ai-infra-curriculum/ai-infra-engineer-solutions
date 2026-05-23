"""NVML-based GPU device inventory."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GPUInfo:
    index: int
    name: str
    compute_capability: tuple[int, int]
    total_mem_gb: float
    free_mem_gb: float
    sm_count: int
    max_threads_per_block: int
    driver_version: str
    mig_enabled: bool
    mig_instances: int


def inventory() -> list[GPUInfo]:
    import pynvml
    pynvml.nvmlInit()
    try:
        driver = pynvml.nvmlSystemGetDriverVersion()
        n = pynvml.nvmlDeviceGetCount()
        out = []
        for i in range(n):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            cc = pynvml.nvmlDeviceGetCudaComputeCapability(h)
            try:
                attrs = pynvml.nvmlDeviceGetAttributes_v2(h)
                sm_count = attrs.multiprocessorCount
                max_threads = attrs.maxThreadsPerBlock
            except Exception:
                sm_count, max_threads = 0, 0
            try:
                mig_mode, _ = pynvml.nvmlDeviceGetMigMode(h)
                mig_enabled = mig_mode == pynvml.NVML_DEVICE_MIG_ENABLE
                mig_count = pynvml.nvmlDeviceGetMaxMigDeviceCount(h) if mig_enabled else 0
            except Exception:
                mig_enabled = False
                mig_count = 0
            out.append(GPUInfo(
                index=i,
                name=pynvml.nvmlDeviceGetName(h),
                compute_capability=cc,
                total_mem_gb=mem.total / 1e9,
                free_mem_gb=mem.free / 1e9,
                sm_count=sm_count,
                max_threads_per_block=max_threads,
                driver_version=driver,
                mig_enabled=mig_enabled,
                mig_instances=mig_count,
            ))
        return out
    finally:
        pynvml.nvmlShutdown()


def nvlink_topology() -> dict[tuple[int, int], str]:
    """Return per-pair link type. Empty dict if unsupported."""
    import pynvml
    pynvml.nvmlInit()
    try:
        out: dict[tuple[int, int], str] = {}
        n = pynvml.nvmlDeviceGetCount()
        if n < 2:
            return out
        for i in range(n):
            for j in range(i + 1, n):
                h1 = pynvml.nvmlDeviceGetHandleByIndex(i)
                h2 = pynvml.nvmlDeviceGetHandleByIndex(j)
                try:
                    link_type = pynvml.nvmlDeviceGetP2PStatus(
                        h1, h2, pynvml.NVML_P2P_CAPS_INDEX_NVLINK,
                    )
                    out[(i, j)] = "NVLINK" if link_type == 0 else "PCIe"
                except Exception:
                    out[(i, j)] = "unknown"
        return out
    finally:
        pynvml.nvmlShutdown()
