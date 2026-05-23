"""Persistent state per onboarded user."""
from __future__ import annotations

import json
import os
from pathlib import Path


def state_dir() -> Path:
    p = Path.home() / ".config" / "ml-onboard"
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_path(user: str) -> Path:
    return state_dir() / f"{user}.json"


def load(user: str) -> dict:
    p = state_path(user)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save(user: str, state: dict) -> None:
    p = state_path(user)
    p.write_text(json.dumps(state, indent=2, default=str))
    os.chmod(p, 0o600)


def write_env(user: str, env: dict[str, str]) -> Path:
    p = state_dir() / f"{user}.env"
    lines = [f"{k}={v}" for k, v in env.items()]
    p.write_text("\n".join(lines) + "\n")
    os.chmod(p, 0o600)
    return p
