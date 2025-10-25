# Step-by-Step Implementation Guide: Python Environment Manager

This guide walks through implementing the Python Environment Manager (pyenvman) from scratch.

## Table of Contents

1. [Project Setup](#project-setup)
2. [Task 1: Python Version Detection](#task-1-python-version-detection)
3. [Task 2: Virtual Environment Manager](#task-2-virtual-environment-manager)
4. [Task 3: Dependency Conflict Resolver](#task-3-dependency-conflict-resolver)
5. [Task 4: Project Scaffolding](#task-4-project-scaffolding)
6. [Task 5: CLI Application](#task-5-cli-application)
7. [Testing](#testing)
8. [Deployment](#deployment)

## Project Setup

### Step 1: Create Project Structure

```bash
mkdir -p src/pyenvman tests scripts docs
touch src/pyenvman/{__init__.py,python_detector.py,venv_manager.py,dependency_resolver.py,project_init.py,cli.py}
touch tests/{test_python_detector.py,test_venv_manager.py,test_dependency_resolver.py,test_project_init.py,test_cli.py,conftest.py}
```

### Step 2: Set Up Dependencies

Create `requirements.txt`:
```
click>=8.1.0
rich>=13.0.0
packaging>=23.0
requests>=2.31.0
```

Create `requirements-dev.txt`:
```
-r requirements.txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
black>=23.0.0
ruff>=0.0.290
mypy>=1.5.0
```

### Step 3: Configure pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pyenvman"
version = "0.1.0"
description = "Advanced Python Environment Manager"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
dependencies = [
    "click>=8.1.0",
    "rich>=13.0.0",
    "packaging>=23.0",
    "requests>=2.31.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.11.0",
    "black>=23.0.0",
    "ruff>=0.0.290",
    "mypy>=1.5.0",
]

[project.scripts]
pyenvman = "pyenvman.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --cov=pyenvman --cov-report=term-missing"

[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

## Task 1: Python Version Detection

### Implementation Overview

The Python detector finds all Python installations on the system by:
1. Searching common system paths
2. Checking for pyenv installations
3. Detecting conda environments
4. Deduplicating and sorting results

### Step 1.1: Define Data Models

In `src/pyenvman/python_detector.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import subprocess
import os
import re

@dataclass
class PythonVersion:
    """Represents a Python installation"""
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
```

### Step 1.2: Implement Detection Logic

```python
class PythonDetector:
    """Detect Python installations on the system"""

    def __init__(self):
        self.found_pythons: List[PythonVersion] = []

    def detect_all(self) -> List[PythonVersion]:
        """Detect all Python installations"""
        pythons = []

        # Detect from various sources
        pythons.extend(self.detect_system_python())
        pythons.extend(self.detect_pyenv())
        pythons.extend(self.detect_conda())

        # Deduplicate
        seen = set()
        unique_pythons = []
        for py in pythons:
            if py not in seen:
                seen.add(py)
                unique_pythons.append(py)

        # Sort by version (newest first)
        unique_pythons.sort(
            key=lambda x: tuple(map(int, x.version.split('.'))),
            reverse=True
        )

        return unique_pythons
```

### Step 1.3: System Python Detection

```python
def detect_system_python(self) -> List[PythonVersion]:
    """Find system Python installations"""
    pythons = []

    # Common system paths
    search_paths = [
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path("/opt/python"),
    ]

    # Windows paths
    if os.name == 'nt':
        search_paths.extend([
            Path("C:/Python*"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python",
        ])

    for search_path in search_paths:
        if not search_path.exists():
            continue

        # Find python executables
        for item in search_path.glob("python*"):
            if item.is_file() and os.access(item, os.X_OK):
                # Skip symlinks that might cause duplicates
                if item.is_symlink():
                    continue

                version_info = self.get_version_info(item)
                if version_info:
                    pythons.append(version_info)

    return pythons
```

### Step 1.4: Get Version Information

```python
def get_version_info(self, python_path: Path) -> Optional[PythonVersion]:
    """Get Python version from executable"""
    try:
        result = subprocess.run(
            [str(python_path), "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Parse version (e.g., "Python 3.11.5")
        version_match = re.search(r'(\d+\.\d+\.\d+)', result.stdout + result.stderr)
        if version_match:
            version = version_match.group(1)

            # Determine manager
            manager = "system"
            if ".pyenv" in str(python_path):
                manager = "pyenv"
            elif "conda" in str(python_path) or "anaconda" in str(python_path):
                manager = "conda"

            return PythonVersion(
                version=version,
                path=python_path,
                manager=manager
            )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    return None
```

## Task 2: Virtual Environment Manager

### Implementation Overview

The venv manager handles:
- Creating venvs with specific Python versions
- Listing all venvs with metadata
- Cloning venvs
- Deleting venvs
- Exporting requirements

### Step 2.1: Initialize VenvManager

In `src/pyenvman/venv_manager.py`:

```python
from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import shutil
import venv
from datetime import datetime
import json

class VenvManager:
    """Manage virtual environments"""

    def __init__(self, venv_dir: Optional[Path] = None):
        self.venv_dir = venv_dir or (Path.home() / ".pyenvman" / "venvs")
        self.venv_dir.mkdir(parents=True, exist_ok=True)

        # Store metadata
        self.metadata_file = self.venv_dir / ".metadata.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load venv metadata"""
        if self.metadata_file.exists():
            with open(self.metadata_file) as f:
                return json.load(f)
        return {}

    def _save_metadata(self) -> None:
        """Save venv metadata"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)
```

### Step 2.2: Create Virtual Environment

```python
def create(
    self,
    name: str,
    python_version: Optional[str] = None,
    requirements: Optional[Path] = None,
    system_site_packages: bool = False
) -> Path:
    """Create a new virtual environment"""
    venv_path = self.venv_dir / name

    if venv_path.exists():
        raise ValueError(f"Virtual environment '{name}' already exists")

    # Find Python executable
    if python_version:
        from .python_detector import PythonDetector
        detector = PythonDetector()
        pythons = detector.detect_all()

        # Find matching version
        python_exe = None
        for py in pythons:
            if py.version.startswith(python_version):
                python_exe = py.path
                break

        if not python_exe:
            raise ValueError(f"Python {python_version} not found")
    else:
        import sys
        python_exe = Path(sys.executable)

    # Create venv
    subprocess.run(
        [str(python_exe), "-m", "venv", str(venv_path)],
        check=True
    )

    # Upgrade pip
    pip_exe = venv_path / "bin" / "pip" if os.name != 'nt' else venv_path / "Scripts" / "pip.exe"
    subprocess.run(
        [str(pip_exe), "install", "--upgrade", "pip", "setuptools", "wheel"],
        check=True,
        capture_output=True
    )

    # Install requirements
    if requirements and requirements.exists():
        subprocess.run(
            [str(pip_exe), "install", "-r", str(requirements)],
            check=True
        )

    # Save metadata
    self.metadata[name] = {
        "created": datetime.now().isoformat(),
        "python_version": self._get_python_version(venv_path),
        "path": str(venv_path)
    }
    self._save_metadata()

    return venv_path
```

### Step 2.3: List Virtual Environments

```python
def list_venvs(self) -> List[Dict[str, Any]]:
    """List all virtual environments"""
    venvs = []

    for venv_path in self.venv_dir.iterdir():
        if venv_path.is_dir() and venv_path.name != ".metadata.json":
            # Check if it's a valid venv
            if self._is_venv(venv_path):
                metadata = self.metadata.get(venv_path.name, {})

                venvs.append({
                    "name": venv_path.name,
                    "path": venv_path,
                    "python_version": metadata.get("python_version", "unknown"),
                    "created": metadata.get("created", "unknown"),
                    "size": self._get_dir_size(venv_path)
                })

    return venvs

def _is_venv(self, path: Path) -> bool:
    """Check if directory is a valid venv"""
    # Check for standard venv structure
    if os.name != 'nt':
        return (path / "bin" / "python").exists()
    else:
        return (path / "Scripts" / "python.exe").exists()

def _get_dir_size(self, path: Path) -> str:
    """Get directory size in human-readable format"""
    total_size = sum(
        f.stat().st_size for f in path.rglob('*') if f.is_file()
    )

    # Convert to MB
    size_mb = total_size / (1024 * 1024)
    return f"{size_mb:.1f} MB"
```

## Task 3: Dependency Conflict Resolver

### Implementation Overview

The dependency resolver:
- Parses requirements.txt files
- Detects version conflicts
- Checks Python version compatibility
- Suggests resolutions
- Generates lockfiles

### Step 3.1: Parse Requirements

In `src/pyenvman/dependency_resolver.py`:

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from packaging.requirements import Requirement
from packaging.version import Version, parse as parse_version
from packaging.specifiers import SpecifierSet
from pathlib import Path
import requests
import re

@dataclass
class PackageInfo:
    """Package metadata"""
    name: str
    version: str
    dependencies: List[str]
    python_requires: Optional[str] = None

@dataclass
class Conflict:
    """Dependency conflict"""
    package: str
    required_by: List[str]
    conflicting_versions: List[str]
    suggestion: Optional[str] = None

class DependencyResolver:
    """Resolve dependency conflicts"""

    def __init__(self):
        self.pypi_url = "https://pypi.org/pypi"
        self._cache: Dict[str, PackageInfo] = {}

    def parse_requirements(self, requirements_file: Path) -> List[Requirement]:
        """Parse requirements.txt file"""
        requirements = []

        with open(requirements_file) as f:
            for line in f:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Skip -r includes (could be recursive)
                if line.startswith('-r '):
                    continue

                # Skip local paths and git URLs for now
                if line.startswith('-e ') or line.startswith('git+'):
                    continue

                try:
                    req = Requirement(line)
                    requirements.append(req)
                except Exception:
                    # Invalid requirement, skip
                    pass

        return requirements
```

### Step 3.2: Detect Conflicts

```python
def detect_conflicts(
    self,
    requirements: List[Requirement],
    python_version: str
) -> List[Conflict]:
    """Detect dependency conflicts"""
    conflicts = []

    # Build dependency graph
    all_deps: Dict[str, List[tuple[str, SpecifierSet]]] = {}

    for req in requirements:
        pkg_name = req.name.lower()

        # Track who requires this package
        if pkg_name not in all_deps:
            all_deps[pkg_name] = []
        all_deps[pkg_name].append(("root", req.specifier))

        # Get package info and dependencies
        try:
            pkg_info = self.get_package_info(req.name)

            # Check Python version compatibility
            if pkg_info.python_requires:
                py_spec = SpecifierSet(pkg_info.python_requires)
                if python_version not in py_spec:
                    conflicts.append(Conflict(
                        package=req.name,
                        required_by=["root"],
                        conflicting_versions=[f"requires {pkg_info.python_requires}"],
                        suggestion=f"Use Python {pkg_info.python_requires}"
                    ))
        except Exception:
            pass

    # Check for version conflicts
    for pkg_name, requirements_list in all_deps.items():
        if len(requirements_list) > 1:
            # Check if specifiers are compatible
            specifiers = [spec for _, spec in requirements_list]
            if not self._are_specifiers_compatible(specifiers):
                conflicts.append(Conflict(
                    package=pkg_name,
                    required_by=[req_by for req_by, _ in requirements_list],
                    conflicting_versions=[str(spec) for spec in specifiers],
                    suggestion=self._suggest_compatible_version(pkg_name, specifiers)
                ))

    return conflicts

def _are_specifiers_compatible(self, specifiers: List[SpecifierSet]) -> bool:
    """Check if version specifiers are compatible"""
    if len(specifiers) <= 1:
        return True

    # Combine all specifiers
    combined = SpecifierSet()
    for spec in specifiers:
        combined &= spec

    # Check if any version satisfies combined specifiers
    # This is a simplified check
    return len(str(combined)) > 0
```

### Step 3.3: Fetch Package Info from PyPI

```python
def get_package_info(
    self,
    package: str,
    version: Optional[str] = None
) -> PackageInfo:
    """Fetch package info from PyPI"""
    cache_key = f"{package}:{version or 'latest'}"
    if cache_key in self._cache:
        return self._cache[cache_key]

    # Fetch from PyPI
    if version:
        url = f"{self.pypi_url}/{package}/{version}/json"
    else:
        url = f"{self.pypi_url}/{package}/json"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()
    info = data.get("info", {})

    # Parse dependencies
    requires_dist = info.get("requires_dist", []) or []
    dependencies = []
    for dep in requires_dist:
        # Simple dependency extraction
        if dep:
            dep_name = dep.split()[0].split('[')[0]
            dependencies.append(dep_name)

    pkg_info = PackageInfo(
        name=package,
        version=version or info.get("version", "unknown"),
        dependencies=dependencies,
        python_requires=info.get("requires_python")
    )

    self._cache[cache_key] = pkg_info
    return pkg_info
```

## Task 4: Project Scaffolding

### Implementation Overview

Project initialization creates:
- Directory structure
- Configuration files (pyproject.toml, .gitignore)
- Template files based on project type
- Git repository
- Virtual environment

### Step 4.1: Initialize Project

In `src/pyenvman/project_init.py`:

```python
from pathlib import Path
from typing import Optional
import subprocess

class ProjectInitializer:
    """Initialize new Python projects"""

    TEMPLATES = {
        "basic": "Basic Python project with tests",
        "fastapi": "FastAPI web service",
        "ml": "Machine learning project with MLflow",
        "cli": "CLI application with click",
    }

    def init_project(
        self,
        path: Path,
        template: str,
        python_version: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """Initialize new project"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        project_name = name or path.name
        project_desc = description or f"A {template} Python project"

        # Create structure
        self.create_structure(path, template)

        # Generate files
        self.generate_readme(path, project_name, project_desc, template)
        self.generate_pyproject_toml(path, project_name, project_desc, python_version)
        self.generate_gitignore(path)

        # Setup git
        self.setup_git(path)

        # Create venv
        from .venv_manager import VenvManager
        venv_mgr = VenvManager()
        venv_mgr.create(project_name, python_version)
```

## Task 5: CLI Application

See complete implementation in the source files.

## Testing

Create comprehensive tests for each module using pytest. See `tests/` directory for examples.

## Deployment

Package and distribute:

```bash
python -m build
python -m twine upload dist/*
```
