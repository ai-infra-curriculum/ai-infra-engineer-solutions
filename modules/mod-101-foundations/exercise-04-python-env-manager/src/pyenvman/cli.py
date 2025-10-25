"""
Command-line interface for pyenvman.

Provides commands for managing Python versions, virtual environments,
dependencies, and project initialization.
"""

import click
from rich.console import Console
from rich.table import Table
from pathlib import Path
import sys

from .python_detector import PythonDetector
from .venv_manager import VenvManager
from .dependency_resolver import DependencyResolver
from .project_init import ProjectInitializer

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """
    pyenvman - Advanced Python Environment Manager

    Manage Python versions, virtual environments, and dependencies with ease.
    """
    pass


@cli.group()
def python() -> None:
    """Manage Python versions."""
    pass


@python.command("list")
def python_list() -> None:
    """List all detected Python versions."""
    detector = PythonDetector()
    pythons = detector.detect_all()

    if not pythons:
        console.print("[yellow]No Python installations found[/yellow]")
        return

    table = Table(title="Python Installations")
    table.add_column("Version", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Manager", style="magenta")

    for py in pythons:
        table.add_row(py.version, str(py.path), py.manager)

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(pythons)} Python installations found")


@cli.group()
def venv() -> None:
    """Manage virtual environments."""
    pass


@venv.command("create")
@click.argument("name")
@click.option("--python", "-p", help="Python version to use")
@click.option(
    "--requirements", "-r", type=click.Path(exists=True), help="Install from requirements.txt"
)
def venv_create(name: str, python: str | None, requirements: str | None) -> None:
    """Create a new virtual environment."""
    try:
        manager = VenvManager()
        req_path = Path(requirements) if requirements else None

        with console.status(f"[bold green]Creating virtual environment '{name}'..."):
            venv_path = manager.create(name, python, req_path)

        console.print(f"[green]✓[/green] Virtual environment created at: {venv_path}")
        console.print(f"\n[bold]To activate:[/bold]")
        console.print(f"  {manager.activate_script(name)}")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}", file=sys.stderr)
        sys.exit(1)


@venv.command("list")
def venv_list() -> None:
    """List all virtual environments."""
    manager = VenvManager()
    venvs = manager.list_venvs()

    if not venvs:
        console.print("[yellow]No virtual environments found[/yellow]")
        return

    table = Table(title="Virtual Environments")
    table.add_column("Name", style="cyan")
    table.add_column("Python", style="green")
    table.add_column("Created", style="magenta")
    table.add_column("Size", justify="right")

    for venv_info in venvs:
        table.add_row(
            venv_info["name"],
            venv_info["python_version"],
            venv_info["created"],
            venv_info["size"],
        )

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(venvs)} virtual environments")


@venv.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def venv_delete(name: str, yes: bool) -> None:
    """Delete a virtual environment."""
    manager = VenvManager()

    if not yes:
        confirmed = click.confirm(f"Delete virtual environment '{name}'?")
        if not confirmed:
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        manager.delete(name)
        console.print(f"[green]✓[/green] Deleted virtual environment: {name}")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}", file=sys.stderr)
        sys.exit(1)


@cli.group()
def deps() -> None:
    """Manage dependencies."""
    pass


@deps.command("check")
@click.argument("requirements", type=click.Path(exists=True))
@click.option("--python", "-p", default="3.11", help="Python version")
def deps_check(requirements: str, python: str) -> None:
    """Check for dependency conflicts."""
    resolver = DependencyResolver()
    req_path = Path(requirements)

    try:
        with console.status("[bold green]Analyzing dependencies..."):
            reqs = resolver.parse_requirements(req_path)
            conflicts = resolver.detect_conflicts(reqs, python)

        if not conflicts:
            console.print("[green]✓ No conflicts detected![/green]")
            return

        console.print(f"[red]✗ Found {len(conflicts)} conflicts:[/red]\n")
        for conflict in conflicts:
            console.print(f"[bold red]Package:[/bold red] {conflict.package}")
            console.print(f"  Required by: {', '.join(conflict.required_by)}")
            console.print(f"  Conflicting versions: {', '.join(conflict.conflicting_versions)}")
            if conflict.suggestion:
                console.print(f"  [green]Suggestion:[/green] {conflict.suggestion}")
            console.print()

        sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}", file=sys.stderr)
        sys.exit(1)


@cli.group()
def project() -> None:
    """Initialize projects."""
    pass


@project.command("init")
@click.argument("path", type=click.Path())
@click.option(
    "--template",
    "-t",
    type=click.Choice(["basic", "fastapi", "ml", "cli"]),
    default="basic",
    help="Project template",
)
@click.option("--name", "-n", help="Project name")
@click.option("--python", "-p", default="3.11", help="Python version")
def project_init(path: str, template: str, name: str | None, python: str) -> None:
    """Initialize a new project."""
    initializer = ProjectInitializer()
    project_path = Path(path)

    try:
        with console.status(f"[bold green]Initializing {template} project..."):
            initializer.init_project(project_path, template, python, name)

        console.print(f"[green]✓[/green] Project initialized at: {project_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  cd {project_path}")
        console.print("  source venv/bin/activate")
        console.print("  pytest tests/")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
