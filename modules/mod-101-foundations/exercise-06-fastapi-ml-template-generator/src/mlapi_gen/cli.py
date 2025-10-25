"""CLI interface for mlapi-gen."""

import click
from pathlib import Path
from rich.console import Console

from .template_engine import TemplateEngine, ProjectConfig

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """mlapi-gen - FastAPI ML Service Template Generator."""
    pass


@cli.command()
@click.argument("name")
@click.option(
    "--template",
    "-t",
    type=click.Choice(
        ["image_classification", "text_classification", "object_detection", "time_series", "generic"]
    ),
    default="generic",
    help="Project template",
)
@click.option("--output", "-o", type=click.Path(), default=".", help="Output directory")
@click.option("--with-auth", is_flag=True, help="Include authentication")
@click.option("--with-monitoring", is_flag=True, help="Include monitoring")
@click.option("--with-rate-limiting", is_flag=True, help="Include rate limiting")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
def generate(
    name: str,
    template: str,
    output: str,
    with_auth: bool,
    with_monitoring: bool,
    with_rate_limiting: bool,
    interactive: bool,
) -> None:
    """Generate ML API project."""
    try:
        # Create config
        config = ProjectConfig(
            name=name,
            description=f"A {template} ML API",
            template_type=template,
            model_path="models/model.pt",
            with_auth=with_auth,
            with_monitoring=with_monitoring,
            with_rate_limiting=with_rate_limiting,
        )

        # Initialize engine
        templates_dir = Path(__file__).parent.parent.parent / "templates"
        engine = TemplateEngine(templates_dir)

        # Validate config
        errors = engine.validate_config(config)
        if errors:
            for error in errors:
                console.print(f"[red]Error:[/red] {error}")
            return

        # Generate project
        output_path = Path(output) / name
        with console.status(f"[bold green]Generating {template} project..."):
            engine.generate_project(config, output_path)

        console.print(f"[green]✓[/green] Project generated at: {output_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  cd {output_path}")
        console.print("  pip install -r requirements.txt")
        console.print("  uvicorn app.main:app --reload")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")


@cli.command()
def list_templates() -> None:
    """List available templates."""
    console.print("[bold]Available Templates:[/bold]\n")
    templates = {
        "image_classification": "Image classification API (CNN models)",
        "text_classification": "Text classification API (BERT, transformers)",
        "object_detection": "Object detection API (YOLO, Faster R-CNN)",
        "time_series": "Time series prediction API",
        "generic": "Generic ML API (customizable)",
    }
    for name, desc in templates.items():
        console.print(f"  [cyan]{name:25}[/cyan] {desc}")


if __name__ == "__main__":
    cli()
