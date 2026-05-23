"""Render all dashboards to JSON for provisioning."""
import importlib.util
import json
from pathlib import Path

from grafanalib._gen import write_dashboard


SRC = Path(__file__).parent / "dashboards"
OUT = Path(__file__).parent / "out"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.dashboard


def main():
    OUT.mkdir(exist_ok=True)
    for p in sorted(SRC.glob("*.dashboard.py")):
        d = _load(p)
        target = OUT / p.name.replace(".dashboard.py", ".json")
        with target.open("w") as f:
            write_dashboard(d, f)
        print(f"rendered {target}")


if __name__ == "__main__":
    main()
