"""Project initialization and scaffolding module."""

from pathlib import Path
from typing import Optional
import subprocess
import logging

logger = logging.getLogger(__name__)


class ProjectInitializer:
    """Initialize new Python projects from templates."""

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
        description: Optional[str] = None,
    ) -> None:
        """Initialize new project from template."""
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

        logger.info(f"Initialized {template} project at {path}")

    def create_structure(self, path: Path, template: str) -> None:
        """Create project directory structure."""
        if template == "basic":
            (path / "src").mkdir(exist_ok=True)
            (path / "src" / "__init__.py").touch()
            (path / "tests").mkdir(exist_ok=True)
            (path / "tests" / "__init__.py").touch()

        elif template == "fastapi":
            (path / "app").mkdir(exist_ok=True)
            (path / "app" / "__init__.py").touch()
            (path / "app" / "main.py").touch()
            (path / "app" / "api").mkdir(exist_ok=True)
            (path / "tests").mkdir(exist_ok=True)

        elif template == "ml":
            (path / "src").mkdir(exist_ok=True)
            (path / "notebooks").mkdir(exist_ok=True)
            (path / "data").mkdir(exist_ok=True)
            (path / "models").mkdir(exist_ok=True)
            (path / "tests").mkdir(exist_ok=True)

        elif template == "cli":
            (path / "src").mkdir(exist_ok=True)
            (path / "src" / "cli.py").touch()
            (path / "tests").mkdir(exist_ok=True)

    def generate_readme(
        self, path: Path, name: str, description: str, template: str
    ) -> None:
        """Generate README.md file."""
        readme_content = f"""# {name}

{description}

## Installation

```bash
pip install -r requirements.txt
```

## Usage

See documentation for usage instructions.

## Testing

```bash
pytest tests/
```

## License

MIT
"""
        (path / "README.md").write_text(readme_content)

    def generate_pyproject_toml(
        self, path: Path, name: str, description: str, python_version: str
    ) -> None:
        """Generate pyproject.toml file."""
        content = f"""[build-system]
requires = ["setuptools>=68.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
requires-python = ">={python_version}"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.black]
line-length = 100
"""
        (path / "pyproject.toml").write_text(content)

    def generate_gitignore(self, path: Path) -> None:
        """Generate .gitignore file."""
        content = """__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
.pytest_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
"""
        (path / ".gitignore").write_text(content)

    def setup_git(self, path: Path) -> None:
        """Initialize git repository."""
        try:
            subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
            logger.info("Initialized git repository")
        except subprocess.CalledProcessError:
            logger.warning("Failed to initialize git repository")
