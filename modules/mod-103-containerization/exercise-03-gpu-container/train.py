"""MNIST training with GPU usage logging."""
import time

import pynvml
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


def gpu_mem_used_gb() -> float:
    pynvml.nvmlInit()
    h = pynvml.nvmlDeviceGetHandleByIndex(0)
    info = pynvml.nvmlDeviceGetMemoryInfo(h)
    pynvml.nvmlShutdown()
    return info.used / 1e9


def main():
    assert torch.cuda.is_available(), "no CUDA device visible — did you pass --gpus all?"
    print(f"device: {torch.cuda.get_device_name(0)}")

    tf = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])
    ds = datasets.MNIST("/tmp/mnist", train=True, download=True, transform=tf)
    loader = DataLoader(ds, batch_size=256, shuffle=True, num_workers=2, pin_memory=True)

    model = nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Linear(64 * 7 * 7, 128), nn.ReLU(), nn.Linear(128, 10),
    ).cuda()

    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(3):
        t0 = time.perf_counter()
        for xb, yb in loader:
            xb, yb = xb.cuda(non_blocking=True), yb.cuda(non_blocking=True)
            loss = loss_fn(model(xb), yb)
            opt.zero_grad(); loss.backward(); opt.step()
        print(f"epoch {epoch} loss={loss.item():.4f} "
              f"time={time.perf_counter()-t0:.1f}s gpu_mem={gpu_mem_used_gb():.2f} GB")


if __name__ == "__main__":
    main()
