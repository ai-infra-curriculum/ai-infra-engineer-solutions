"""ResNet-18 + AMP + gradient accumulation + cosine LR + safetensors ckpts."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn as nn
from safetensors.torch import save_file, load_file
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.models import resnet18


def get_loaders(batch_size: int, num_workers: int = 4) -> tuple[DataLoader, DataLoader]:
    mean = (0.4914, 0.4822, 0.4465)
    std = (0.2470, 0.2435, 0.2616)
    train_tf = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    test_tf = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mean, std)])
    train_ds = datasets.CIFAR10("data", train=True, download=True, transform=train_tf)
    test_ds = datasets.CIFAR10("data", train=False, download=True, transform=test_tf)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                                num_workers=num_workers, pin_memory=True,
                                persistent_workers=num_workers > 0)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False,
                              num_workers=num_workers, pin_memory=True,
                              persistent_workers=num_workers > 0)
    return train_loader, test_loader


def save_ckpt(epoch: int, model, opt, sched, scaler, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    save_file(model.state_dict(), str(path) + ".safetensors")
    torch.save({
        "epoch": epoch,
        "opt": opt.state_dict(),
        "sched": sched.state_dict(),
        "scaler": scaler.state_dict(),
    }, str(path) + ".aux.pt")


def load_ckpt(path: Path, model, opt, sched, scaler) -> int:
    model.load_state_dict(load_file(str(path) + ".safetensors"))
    aux = torch.load(str(path) + ".aux.pt", weights_only=True)
    opt.load_state_dict(aux["opt"])
    sched.load_state_dict(aux["sched"])
    scaler.load_state_dict(aux["scaler"])
    return aux["epoch"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--accum", type=int, default=1)
    p.add_argument("--lr", type=float, default=0.1)
    p.add_argument("--num-workers", type=int, default=4)
    p.add_argument("--resume", default=None)
    args = p.parse_args()

    device = torch.device("cuda")
    train_loader, _ = get_loaders(args.batch_size, args.num_workers)
    model = resnet18(num_classes=10).to(device)
    opt = torch.optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, weight_decay=5e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda")
    loss_fn = nn.CrossEntropyLoss()

    start = 0
    if args.resume:
        start = load_ckpt(Path(args.resume), model, opt, sched, scaler) + 1

    for epoch in range(start, args.epochs):
        model.train()
        t0 = time.perf_counter()
        running_loss = 0.0
        steps = 0
        for step, (xb, yb) in enumerate(train_loader):
            xb = xb.to(device, non_blocking=True)
            yb = yb.to(device, non_blocking=True)
            with torch.amp.autocast("cuda", dtype=torch.float16):
                loss = loss_fn(model(xb), yb) / args.accum
            scaler.scale(loss).backward()
            running_loss += loss.item() * args.accum
            steps += 1
            if (step + 1) % args.accum == 0:
                scaler.step(opt); scaler.update()
                opt.zero_grad(set_to_none=True)
        sched.step()
        save_ckpt(epoch, model, opt, sched, scaler, Path(f"models/epoch-{epoch}"))
        print(json.dumps({"epoch": epoch, "loss": running_loss/steps,
                          "time_s": round(time.perf_counter()-t0, 2)}))

    save_ckpt(args.epochs - 1, model, opt, sched, scaler, Path("models/epoch-final"))


if __name__ == "__main__":
    main()
