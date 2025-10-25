"""Template generation engine."""

from pathlib import Path
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass
import black
import isort
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProjectConfig:
    """Project configuration."""

    name: str
    description: str
    template_type: str  # "image_classification", "text_classification", etc.
    model_path: str
    input_schema: Dict[str, Any] = None
    output_schema: Dict[str, Any] = None
    python_version: str = "3.11"
    with_auth: bool = False
    with_rate_limiting: bool = False
    with_monitoring: bool = True

    def __post_init__(self) -> None:
        if self.input_schema is None:
            self.input_schema = {}
        if self.output_schema is None:
            self.output_schema = {}


class TemplateEngine:
    """Generate ML API projects from templates."""

    def __init__(self, templates_dir: Path) -> None:
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(templates_dir), trim_blocks=True, lstrip_blocks=True
        )

    def generate_project(self, config: ProjectConfig, output_dir: Path) -> None:
        """Generate complete project from template."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create directory structure
        self.create_directory_structure(output_dir, config.template_type)

        # Generate files
        context = self._create_context(config)
        self._generate_files(output_dir, context)

        logger.info(f"Generated project at {output_dir}")

    def create_directory_structure(self, output_dir: Path, template_type: str) -> None:
        """Create project directory structure."""
        dirs = [
            output_dir / "app",
            output_dir / "app" / "api",
            output_dir / "app" / "models",
            output_dir / "app" / "core",
            output_dir / "tests",
            output_dir / "models",
            output_dir / ".github" / "workflows",
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            if "app" in str(dir_path) or "tests" in str(dir_path):
                (dir_path / "__init__.py").touch()

    def _create_context(self, config: ProjectConfig) -> Dict[str, Any]:
        """Create template context from config."""
        return {
            "project_name": config.name,
            "project_description": config.description,
            "template_type": config.template_type,
            "model_path": config.model_path,
            "python_version": config.python_version,
            "with_auth": config.with_auth,
            "with_rate_limiting": config.with_rate_limiting,
            "with_monitoring": config.with_monitoring,
            "input_schema": config.input_schema,
            "output_schema": config.output_schema,
        }

    def _generate_files(self, output_dir: Path, context: Dict[str, Any]) -> None:
        """Generate all project files."""
        # Generate README
        self._render_and_save("README.md.j2", output_dir / "README.md", context)

        # Generate requirements
        self._render_and_save(
            "requirements.txt.j2", output_dir / "requirements.txt", context
        )

        # Generate Dockerfile
        self._render_and_save("Dockerfile.j2", output_dir / "Dockerfile", context)

        logger.info("Generated all project files")

    def _render_and_save(
        self, template_name: str, output_path: Path, context: Dict[str, Any]
    ) -> None:
        """Render template and save to file."""
        try:
            template = self.env.get_template(template_name)
            content = template.render(**context)

            # Format Python files
            if output_path.suffix == ".py":
                content = black.format_str(content, mode=black.Mode())
                content = isort.code(content)

            output_path.write_text(content)
        except Exception as e:
            logger.error(f"Failed to render {template_name}: {e}")

    def validate_config(self, config: ProjectConfig) -> List[str]:
        """Validate project configuration."""
        errors = []

        # Validate name
        if not config.name.replace("-", "").replace("_", "").isalnum():
            errors.append("Project name must be alphanumeric with dashes/underscores")

        # Validate template type
        valid_templates = [
            "image_classification",
            "text_classification",
            "object_detection",
            "time_series",
            "generic",
        ]
        if config.template_type not in valid_templates:
            errors.append(f"Template must be one of: {', '.join(valid_templates)}")

        return errors
