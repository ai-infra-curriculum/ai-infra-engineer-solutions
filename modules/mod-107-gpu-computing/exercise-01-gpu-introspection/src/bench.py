"""matmul TFLOPS + memcpy bandwidth benchmarks."""
from __future__ import annotations

import time


def matmul_tflops(device: int, n: int = 2048, repeat: int = 50) -> float:
    import torch
    dev = torch.device(f"cuda:{device}")
    a = torch.randn(n, n, device=dev, dtype=torch.float32)
    b = torch.randn(n, n, device=dev, dtype=torch.float32)
    for _ in range(5):
        torch.matmul(a, b); torch.cuda.synchronize(dev)
    t0 = time.perf_counter()
    for _ in range(repeat):
        torch.matmul(a, b); torch.cuda.synchronize(dev)
    elapsed = time.perf_counter() - t0
    flops = 2 * n ** 3 * repeat
    return flops / elapsed / 1e12


def bandwidth_gbs(device: int, size_mb: int = 512) -> float:
    import torch
    dev = torch.device(f"cuda:{device}")
    n = size_mb * 1024 * 256  # 4-byte floats
    src = torch.randn(n, device=dev)
    dst = torch.empty_like(src)
    for _ in range(3):
        dst.copy_(src); torch.cuda.synchronize(dev)
    t0 = time.perf_counter()
    for _ in range(10):
        dst.copy_(src); torch.cuda.synchronize(dev)
    elapsed = time.perf_counter() - t0
    return (src.element_size() * src.numel() * 10) / elapsed / 1e9
