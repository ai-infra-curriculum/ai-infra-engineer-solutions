"""Inference benchmark."""
from __future__ import annotations

import argparse
import time

import torch
from safetensors.torch import load_file
from torchvision.models import resnet18


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt", required=True)
    args = p.parse_args()

    model = resnet18(num_classes=10).cuda()
    model.load_state_dict(load_file(args.ckpt + ".safetensors"))
    model.train(False)

    for bs in (1, 16, 128):
        x = torch.randn(bs, 3, 32, 32, device="cuda")
        with torch.inference_mode():
            for _ in range(5): model(x); torch.cuda.synchronize()
            t0 = time.perf_counter()
            for _ in range(50): model(x); torch.cuda.synchronize()
            elapsed = time.perf_counter() - t0
        print(f"bs={bs:3d}  throughput={bs*50/elapsed:7.0f} img/s  "
              f"lat/img={elapsed/(50*bs)*1000:.2f}ms")


if __name__ == "__main__":
    main()
