"""Consistent variant assignment via hashing."""
from __future__ import annotations

import hashlib


def assign(user_id: int, experiment_id: str, variants: dict[str, float]) -> str:
    """Return variant name. Same (user_id, experiment_id) always returns same variant."""
    h = hashlib.md5(f"{experiment_id}:{user_id}".encode()).hexdigest()
    # Map first 8 hex chars to [0, 1)
    pos = int(h[:8], 16) / 0xFFFFFFFF
    cum = 0.0
    for name, weight in variants.items():
        cum += weight
        if pos < cum:
            return name
    return next(iter(variants))


def test():
    # Stability: same user always gets same variant
    variants = {"control": 0.5, "treatment": 0.5}
    a = [assign(uid, "exp1", variants) for uid in range(10000)]
    b = [assign(uid, "exp1", variants) for uid in range(10000)]
    assert a == b
    # Distribution: roughly 50/50
    p_treat = sum(1 for v in a if v == "treatment") / len(a)
    assert 0.48 < p_treat < 0.52, f"unbalanced: {p_treat}"
    print("ok")


if __name__ == "__main__":
    test()
