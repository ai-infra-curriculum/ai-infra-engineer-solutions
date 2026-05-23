"""Async continuous batcher: aggregate up to 32 requests for 20ms windows."""
import asyncio
import time

import torch
from torchvision.models import resnet50, ResNet50_Weights


MAX_BATCH = 32
WINDOW_MS = 20


class Batcher:
    def __init__(self, model):
        self.model = model
        self.queue: asyncio.Queue = asyncio.Queue()

    async def predict(self, x: torch.Tensor) -> torch.Tensor:
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        await self.queue.put((x, fut))
        return await fut

    async def loop(self):
        while True:
            items = [await self.queue.get()]
            deadline = time.monotonic() + WINDOW_MS / 1000
            while len(items) < MAX_BATCH:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    break
                try:
                    items.append(await asyncio.wait_for(self.queue.get(), timeout))
                except asyncio.TimeoutError:
                    break

            xs = torch.stack([i[0] for i in items]).cuda()
            with torch.inference_mode():
                preds = self.model(xs)
            for (_, fut), p in zip(items, preds):
                fut.set_result(p)


async def main():
    model = resnet50(weights=ResNet50_Weights.DEFAULT).cuda()
    model.train(False)
    batcher = Batcher(model)
    asyncio.create_task(batcher.loop())

    async def client(i):
        x = torch.randn(3, 224, 224, device="cuda")
        t0 = time.perf_counter()
        await batcher.predict(x)
        return (time.perf_counter() - t0) * 1000

    # 100 concurrent clients
    latencies = await asyncio.gather(*[client(i) for i in range(100)])
    latencies.sort()
    print(f"p50: {latencies[50]:.1f}ms  p95: {latencies[95]:.1f}ms  p99: {latencies[99]:.1f}ms")


if __name__ == "__main__":
    asyncio.run(main())
