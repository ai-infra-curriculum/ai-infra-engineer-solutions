"""Virtual environment management module."""

from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import shutil
import os
import json
import sys
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class VenvManager:
    """Manage virtual environments."""

    def __init__(self, venv_dir: Optional[Path] = None) -> None:
        """Initialize VenvManager with storage directory."""
        self.venv_dir = venv_dir or (Path.home() / ".pyenvman" / "venvs")
        self.venv_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.venv_dir / ".metadata.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load venv metadata from file."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Failed to load metadata, starting fresh")
        return {}

    def _save_metadata(self) -> None:
        """Save venv metadata to file."""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2, default=str)

    def create(
        self,
        name: str,
        python_version: Optional[str] = None,
        requirements: Optional[Path] = None,
        system_site_packages: bool = False,
    ) -> Path:
        """Create a new virtual environment."""
        venv_path = self.venv_dir / name

        if venv_path.exists():
            raise ValueError(f"Virtual environment '{name}' already exists")

        # Find Python executable
        if python_version:
            from .python_detector import PythonDetector

            detector = PythonDetector()
            pythons = detector.detect_all()
            python_exe = None
            for py in pythons:
                if py.version.startswith(python_version):
                    python_exe = py.path
                    break
            if not python_exe:
                raise ValueError(f"Python {python_version} not found")
        else:
            python_exe = Path(sys.executable)

        # Create venv
        subprocess.run([str(python_exe), "-m", "venv", str(venv_path)], check=True)

        # Get pip path
        pip_exe = self._get_pip_path(venv_path)

        # Upgrade pip
        subprocess.run(
            [str(pip_exe), "install", "--upgrade", "pip", "setuptools", "wheel"],
            check=True,
            capture_output=True,
        )

        # Install requirements
        if requirements and requirements.exists():
            subprocess.run([str(pip_exe), "install", "-r", str(requirements)], check=True)

        # Save metadata
        self.metadata[name] = {
            "created": datetime.now().isoformat(),
            "python_version": self._get_python_version(venv_path),
            "path": str(venv_path),
        }
        self._save_metadata()

        logger.info(f"Created virtual environment: {name}")
        return venv_path

    def list_venvs(self) -> List[Dict[str, Any]]:
        """List all virtual environments."""
        venvs = []

        for item in self.venv_dir.iterdir():
            if item.is_dir() and item.name not in [".metadata.json"]:
                if self._is_venv(item):
                    metadata = self.metadata.get(item.name, {})
                    venvs.append(
                        {
                            "name": item.name,
                            "path": item,
                            "python_version": metadata.get("python_version", "unknown"),
                            "created": metadata.get("created", "unknown"),
                            "size": self._get_dir_size(item),
                        }
                    )

        return sorted(venvs, key=lambda x: x["name"])

    def delete(self, name: str, confirm: bool = True) -> bool:
        """Delete virtual environment."""
        venv_path = self.venv_dir / name

        if not venv_path.exists():
            raise ValueError(f"Virtual environment '{name}' not found")

        shutil.rmtree(venv_path)

        # Remove metadata
        if name in self.metadata:
            del self.metadata[name]
            self._save_metadata()

        logger.info(f"Deleted virtual environment: {name}")
        return True

    def activate_script(self, name: str) -> str:
        """Generate activation command for virtual environment."""
        venv_path = self.venv_dir / name

        if not venv_path.exists():
            raise ValueError(f"Virtual environment '{name}' not found")

        if os.name == "nt":
            return f"{venv_path}\\Scripts\\activate.bat"
        else:
            return f"source {venv_path}/bin/activate"

    def _is_venv(self, path: Path) -> bool:
        """Check if directory is a valid venv."""
        if os.name == "nt":
            return (path / "Scripts" / "python.exe").exists()
        else:
            return (path / "bin" / "python").exists()

    def _get_pip_path(self, venv_path: Path) -> Path:
        """Get pip executable path in venv."""
        if os.name == "nt":
            return venv_path / "Scripts" / "pip.exe"
        else:
            return venv_path / "bin" / "pip"

    def _get_python_version(self, venv_path: Path) -> str:
        """Get Python version in venv."""
        python_exe = venv_path / "bin" / "python" if os.name != "nt" else venv_path / "Scripts" / "python.exe"
        try:
            result = subprocess.run(
                [str(python_exe), "--version"], capture_output=True, text=True, timeout=5
            )
            import re

            match = re.search(r"(\d+\.\d+\.\d+)", result.stdout + result.stderr)
            return match.group(1) if match else "unknown"
        except Exception:
            return "unknown"

    def _get_dir_size(self, path: Path) -> str:
        """Get directory size in human-readable format."""
        total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)
        return f"{size_mb:.1f} MB"
