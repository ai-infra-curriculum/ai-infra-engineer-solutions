"""Smoke test: just verifies the CLI parses + handles 'no GPU' gracefully."""
import subprocess
import sys


def test_no_gpu_exits_2(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    r = subprocess.run([sys.executable, "-m", "src.cli", "--no-bench"], capture_output=True)
    assert r.returncode == 2


def test_json_mode_parses(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    r = subprocess.run([sys.executable, "-m", "src.cli", "--json", "--no-bench"], capture_output=True)
    # exit code 2 but if any output, should be JSON-parseable
    if r.stdout.strip():
        import json
        json.loads(r.stdout)
