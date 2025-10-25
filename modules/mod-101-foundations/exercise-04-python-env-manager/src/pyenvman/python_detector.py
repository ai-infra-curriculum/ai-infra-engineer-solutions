"""
Python version detection module.

Detects Python installations from system paths, pyenv, conda, and other sources.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import subprocess
import os
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class PythonVersion:
    """Represents a Python installation."""

    version: str  # e.g., "3.11.5"
    path: Path
    manager: str  # "system", "pyenv", "conda", "asdf"
    is_virtual: bool = False

    def __hash__(self) -> int:
        return hash((self.version, str(self.path)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PythonVersion):
            return False
        return self.version == other.version and self.path == other.path


class PythonDetector:
    """Detect Python installations on the system."""

    def __init__(self) -> None:
        self.found_pythons: List[PythonVersion] = []

    def detect_all(self) -> List[PythonVersion]:
        """
        Detect all Python installations.

        Returns:
            List of PythonVersion objects, sorted by version (newest first).
        """
        pythons = []

        # Detect from various sources
        pythons.extend(self.detect_system_python())
        pythons.extend(self.detect_pyenv())
        pythons.extend(self.detect_conda())

        # Deduplicate based on version and path
        seen = set()
        unique_pythons = []
        for py in pythons:
            if py not in seen:
                seen.add(py)
                unique_pythons.append(py)

        # Sort by version (newest first)
        unique_pythons.sort(key=lambda x: self._version_tuple(x.version), reverse=True)

        logger.info(f"Found {len(unique_pythons)} unique Python installations")
        return unique_pythons

    def detect_system_python(self) -> List[PythonVersion]:
        """Find system Python installations."""
        pythons = []

        # Common system paths
        search_paths = [
            Path("/usr/bin"),
            Path("/usr/local/bin"),
            Path("/opt/python"),
        ]

        # Windows paths
        if os.name == "nt":
            app_data = os.environ.get("LOCALAPPDATA", "")
            search_paths.extend(
                [
                    Path("C:/Python*"),
                    Path(app_data) / "Programs" / "Python" if app_data else None,
                ]
            )

        # Filter out None values
        search_paths = [p for p in search_paths if p is not None]

        for search_path in search_paths:
            if not search_path.exists():
                continue

            # Find python executables
            pattern = "python*" if os.name != "nt" else "python*.exe"
            for item in search_path.glob(pattern):
                if item.is_file() and os.access(item, os.X_OK):
                    # Skip symlinks to avoid duplicates
                    if item.is_symlink():
                        continue

                    # Skip python-config and similar tools
                    if "config" in item.name or item.name.endswith("-config"):
                        continue

                    version_info = self.get_version_info(item)
                    if version_info:
                        pythons.append(version_info)

        return pythons

    def detect_pyenv(self) -> List[PythonVersion]:
        """Find pyenv Python installations."""
        pythons = []

        pyenv_root = Path.home() / ".pyenv" / "versions"
        if not pyenv_root.exists():
            return pythons

        for version_dir in pyenv_root.iterdir():
            if not version_dir.is_dir():
                continue

            # Find python executable in pyenv version
            python_path = version_dir / "bin" / "python"
            if python_path.exists():
                version_info = self.get_version_info(python_path)
                if version_info:
                    version_info.manager = "pyenv"
                    pythons.append(version_info)

        return pythons

    def detect_conda(self) -> List[PythonVersion]:
        """Find conda Python environments."""
        pythons = []

        # Try to find conda environments
        conda_paths = [
            Path.home() / ".conda" / "envs",
            Path.home() / "anaconda3" / "envs",
            Path.home() / "miniconda3" / "envs",
            Path("/opt/conda/envs"),
        ]

        for conda_path in conda_paths:
            if not conda_path.exists():
                continue

            for env_dir in conda_path.iterdir():
                if not env_dir.is_dir():
                    continue

                # Find python in conda env
                if os.name == "nt":
                    python_path = env_dir / "python.exe"
                else:
                    python_path = env_dir / "bin" / "python"

                if python_path.exists():
                    version_info = self.get_version_info(python_path)
                    if version_info:
                        version_info.manager = "conda"
                        pythons.append(version_info)

        return pythons

    def get_version_info(self, python_path: Path) -> Optional[PythonVersion]:
        """
        Get Python version from executable.

        Args:
            python_path: Path to Python executable

        Returns:
            PythonVersion object or None if version cannot be determined
        """
        try:
            result = subprocess.run(
                [str(python_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Parse version (e.g., "Python 3.11.5")
            version_output = result.stdout + result.stderr
            version_match = re.search(r"(\d+\.\d+\.\d+)", version_output)

            if version_match:
                version = version_match.group(1)

                # Determine manager based on path
                manager = "system"
                path_str = str(python_path)

                if ".pyenv" in path_str:
                    manager = "pyenv"
                elif "conda" in path_str or "anaconda" in path_str:
                    manager = "conda"
                elif ".asdf" in path_str:
                    manager = "asdf"

                return PythonVersion(
                    version=version, path=python_path.resolve(), manager=manager
                )

        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            FileNotFoundError,
        ) as e:
            logger.debug(f"Failed to get version for {python_path}: {e}")

        return None

    @staticmethod
    def _version_tuple(version: str) -> tuple:
        """Convert version string to tuple for comparison."""
        try:
            return tuple(map(int, version.split(".")))
        except ValueError:
            return (0, 0, 0)
