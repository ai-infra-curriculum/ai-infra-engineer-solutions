"""Load active prompt by id; resolves through symlink."""
from pathlib import Path

import yaml


BASE = Path(__file__).parent / "prompts"


def load(prompt_id: str) -> dict:
    return yaml.safe_load((BASE / prompt_id / "active.yaml").read_text())


def render(prompt_id: str, **kwargs) -> dict:
    spec = load(prompt_id)
    return {
        "model": spec["model"],
        "temperature": spec.get("temperature", 0),
        "prompt": spec["template"].format(**kwargs),
        "schema": spec.get("schema"),
    }
