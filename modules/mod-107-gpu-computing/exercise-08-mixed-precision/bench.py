"""Cross-precision training benchmark."""
from __future__ import annotations

import argparse
import time

import torch
import torch.nn as nn


PRECISIONS = {
    "fp32": (None, False),
    "tf32": (None, True),
    "fp16": (torch.float16, False),
    "bf16": (torch.bfloat16, False),
}


def build_model(name: str):
    if name == "resnet50":
        from torchvision.models import resnet50
        return resnet50(num_classes=1000)
    elif name == "transformer":
        return nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=512, nhead=8, dim_feedforward=2048,
                                        batch_first=True),
            num_layers=6,
        )
    raise ValueError(name)


def synthetic_batch(name: str, batch_size: int):
    if name == "resnet50":
        x = torch.randn(batch_size, 3, 224, 224, device="cuda")
        y = torch.randint(0, 1000, (batch_size,), device="cuda")
        return x, y
    x = torch.randn(batch_size, 128, 512, device="cuda")
    return x, None


def step(model, opt, scaler, x, y, dtype, model_name):
    if dtype:
        with torch.amp.autocast("cuda", dtype=dtype):
            out = model(x)
            if model_name == "resnet50":
                loss = nn.functional.cross_entropy(out, y)
            else:
                loss = out.sum()
        if scaler:
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update()
        else:
            loss.backward(); opt.step()
    else:
        out = model(x)
        loss = nn.functional.cross_entropy(out, y) if model_name == "resnet50" else out.sum()
        loss.backward(); opt.step()
    opt.zero_grad()
    return loss.item()


def bench_one(model_name: str, precision: str, batch_size: int, steps: int = 30) -> dict:
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    dtype, tf32 = PRECISIONS[precision]
    torch.backends.cuda.matmul.allow_tf32 = tf32
    torch.backends.cudnn.allow_tf32 = tf32

    model = build_model(model_name).cuda().train()
    opt = torch.optim.SGD(model.parameters(), lr=0.01)
    scaler = torch.amp.GradScaler("cuda") if dtype is torch.float16 else None

    x, y = synthetic_batch(model_name, batch_size)
    for _ in range(3):
        step(model, opt, scaler, x, y, dtype, model_name)
        torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(steps):
        step(model, opt, scaler, x, y, dtype, model_name)
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0

    return {
        "ms_per_step": elapsed / steps * 1000,
        "throughput": batch_size * steps / elapsed,
        "peak_gb": torch.cuda.max_memory_allocated() / 1e9,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="resnet50", choices=list(["resnet50", "transformer"]))
    p.add_argument("--batch-sizes", default="32,128,512")
    args = p.parse_args()

    sizes = [int(b) for b in args.batch_sizes.split(",")]
    print(f"{'precision':<10} {'bs':>5} {'ms/step':>10} {'throughput':>12} {'peak_gb':>10}")
    for prec in ("fp32", "tf32", "bf16", "fp16"):
        for bs in sizes:
            try:
                r = bench_one(args.model, prec, bs)
                print(f"{prec:<10} {bs:>5} {r['ms_per_step']:>10.1f} {r['throughput']:>12.1f} {r['peak_gb']:>10.2f}")
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    print(f"{prec:<10} {bs:>5}  OOM")
                else:
                    raise


if __name__ == "__main__":
    main()
