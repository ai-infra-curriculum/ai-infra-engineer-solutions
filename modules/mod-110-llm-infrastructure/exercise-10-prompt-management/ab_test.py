"""Per-request A/B between two prompt versions (hash-based)."""
import hashlib

import yaml


SPLITS = yaml.safe_load(open("ab.yaml"))
# Example ab.yaml:
# classify_intent:
#   experiment_id: 2026-05
#   v1: 50
#   v2: 50


def pick_version(prompt_id: str, user_id: str) -> int:
    cfg = SPLITS[prompt_id]
    exp = cfg["experiment_id"]
    h = int(hashlib.md5(f"{exp}:{user_id}".encode()).hexdigest()[:8], 16)
    bucket = h % 100
    cum = 0
    for k, weight in cfg.items():
        if not k.startswith("v"):
            continue
        cum += weight
        if bucket < cum:
            return int(k[1:])
    return 1
