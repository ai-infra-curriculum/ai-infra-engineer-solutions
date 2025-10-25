"""Dependency conflict resolution module."""

from dataclasses import dataclass
from typing import List, Dict, Optional
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from pathlib import Path
import requests
import logging

logger = logging.getLogger(__name__)


@dataclass
class PackageInfo:
    """Package metadata from PyPI."""

    name: str
    version: str
    dependencies: List[str]
    python_requires: Optional[str] = None


@dataclass
class Conflict:
    """Dependency conflict information."""

    package: str
    required_by: List[str]
    conflicting_versions: List[str]
    suggestion: Optional[str] = None


class DependencyResolver:
    """Resolve dependency conflicts."""

    def __init__(self) -> None:
        self.pypi_url = "https://pypi.org/pypi"
        self._cache: Dict[str, PackageInfo] = {}

    def parse_requirements(self, requirements_file: Path) -> List[Requirement]:
        """Parse requirements.txt file."""
        requirements = []

        with open(requirements_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("-r ") or line.startswith("-e ") or line.startswith("git+"):
                    continue

                try:
                    req = Requirement(line)
                    requirements.append(req)
                except Exception as e:
                    logger.warning(f"Failed to parse requirement: {line} - {e}")

        return requirements

    def detect_conflicts(
        self, requirements: List[Requirement], python_version: str
    ) -> List[Conflict]:
        """Detect dependency conflicts."""
        conflicts = []
        all_deps: Dict[str, List[tuple[str, SpecifierSet]]] = {}

        for req in requirements:
            pkg_name = req.name.lower()
            if pkg_name not in all_deps:
                all_deps[pkg_name] = []
            all_deps[pkg_name].append(("root", req.specifier))

        # Check for version conflicts
        for pkg_name, requirements_list in all_deps.items():
            if len(requirements_list) > 1:
                specifiers = [spec for _, spec in requirements_list]
                if not self._are_specifiers_compatible(specifiers):
                    conflicts.append(
                        Conflict(
                            package=pkg_name,
                            required_by=[req_by for req_by, _ in requirements_list],
                            conflicting_versions=[str(spec) for spec in specifiers],
                            suggestion=f"Consider using a compatible version range for {pkg_name}",
                        )
                    )

        return conflicts

    def get_package_info(
        self, package: str, version: Optional[str] = None
    ) -> PackageInfo:
        """Fetch package info from PyPI."""
        cache_key = f"{package}:{version or 'latest'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = f"{self.pypi_url}/{package}/json" if not version else f"{self.pypi_url}/{package}/{version}/json"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            info = data.get("info", {})

            requires_dist = info.get("requires_dist", []) or []
            dependencies = []
            for dep in requires_dist:
                if dep:
                    dep_name = dep.split()[0].split("[")[0]
                    dependencies.append(dep_name)

            pkg_info = PackageInfo(
                name=package,
                version=version or info.get("version", "unknown"),
                dependencies=dependencies,
                python_requires=info.get("requires_python"),
            )

            self._cache[cache_key] = pkg_info
            return pkg_info

        except Exception as e:
            logger.error(f"Failed to fetch package info for {package}: {e}")
            raise

    def _are_specifiers_compatible(self, specifiers: List[SpecifierSet]) -> bool:
        """Check if version specifiers are compatible."""
        if len(specifiers) <= 1:
            return True

        # Simple compatibility check - could be enhanced
        combined = str(specifiers[0])
        for spec in specifiers[1:]:
            if str(spec) != combined:
                return False
        return True
