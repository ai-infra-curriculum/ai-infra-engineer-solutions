"""Benchmark custom kernel vs torch.add."""
import time

import torch
import my_ops


def bench(fn, *args, iters=100):
    for _ in range(5): fn(*args); torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters): fn(*args); torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters * 1000


def main():
    for n in (10_000, 1_000_000, 100_000_000):
        a = torch.randn(n, device="cuda")
        b = torch.randn_like(a)
        # correctness
        torch.testing.assert_close(my_ops.add(a, b), a + b)
        my_ms = bench(my_ops.add, a, b)
        torch_ms = bench(torch.add, a, b)
        print(f"n={n:>10}  my={my_ms:7.3f}ms  torch={torch_ms:7.3f}ms  ratio={torch_ms/my_ms:.2f}x")


if __name__ == "__main__":
    main()
