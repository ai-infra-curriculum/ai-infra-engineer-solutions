"""Measure cache hit rate + cost savings on a synthetic workload."""
from __future__ import annotations

import random
import time

from cache import SemanticCache


# Synthetic: 100 distinct intents, each phrased ~15 different ways
INTENTS = [
    ["how do I reset my password", "reset password help", "I forgot my password",
      "can you help me change my password", "lost password reset link"],
    ["what's the weather", "tell me the weather", "weather today", "current weather",
      "is it raining"],
    # ... (full workload would have hundreds)
]


def main():
    c = SemanticCache()
    hits = 0
    misses = 0
    cost_per_miss = 0.002
    cost_per_hit = 0.0001         # embedding lookup is ~20× cheaper
    total_cost = 0.0

    requests = []
    for intent_group in INTENTS:
        for _ in range(20):       # 20 calls per intent
            requests.append(random.choice(intent_group))

    random.shuffle(requests)

    for q in requests:
        hit = c.get(q)
        if hit:
            hits += 1
            total_cost += cost_per_hit
        else:
            misses += 1
            total_cost += cost_per_miss
            response = f"<llm response to: {q}>"
            c.put(q, response)

    print(f"Total requests: {hits + misses}")
    print(f"Hit rate: {hits / (hits + misses) * 100:.1f}%")
    print(f"Total cost: ${total_cost:.2f}")
    print(f"Vs no cache: ${(hits + misses) * cost_per_miss:.2f}")
    print(f"Savings: {(1 - total_cost / ((hits + misses) * cost_per_miss)) * 100:.1f}%")


if __name__ == "__main__":
    main()
