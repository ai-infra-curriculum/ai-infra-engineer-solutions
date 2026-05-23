"""Cumulative inference optimization benchmark for ResNet-50."""
import time

import torch
from torchvision.models import resnet50, ResNet50_Weights


def bench(fn, x, iters=100):
    with torch.inference_mode():
        for _ in range(5): fn(x); torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(iters): fn(x); torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters * 1000


def main():
    model = resnet50(weights=ResNet50_Weights.DEFAULT).cuda()
    model.train(False)
    x = torch.randn(1, 3, 224, 224, device="cuda")

    print(f"baseline fp32:      {bench(model, x):.2f}ms")

    compiled = torch.compile(model, mode="reduce-overhead")
    print(f"+torch.compile:     {bench(compiled, x):.2f}ms")

    model_bf16 = model.to(torch.bfloat16)
    x_bf16 = x.to(torch.bfloat16)
    print(f"+bf16:              {bench(model_bf16, x_bf16):.2f}ms")

    compiled_bf16 = torch.compile(model_bf16, mode="reduce-overhead")
    print(f"+compile+bf16:      {bench(compiled_bf16, x_bf16):.2f}ms")

    try:
        import torch_tensorrt
        trt = torch_tensorrt.compile(
            model.float().cuda(),
            inputs=[torch_tensorrt.Input(shape=[1, 3, 224, 224], dtype=torch.float16)],
            enabled_precisions={torch.float16},
        )
        print(f"+TensorRT fp16:     {bench(trt, x.half()):.2f}ms")
    except Exception as e:
        print(f"TensorRT skipped: {e}")


if __name__ == "__main__":
    main()
