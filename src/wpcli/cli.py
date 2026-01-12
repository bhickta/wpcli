import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .wizard import run_wizard
from .generator import ProjectGenerator

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="wpcli")
def cli() -> None:
    """WordPress Ansible CLI - Production-ready WordPress deployment tool."""
    pass


@cli.command()
@click.option(
    "--output",
    "-o",
    default="wordpress-ansible",
    help="Output directory for generated project",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to YAML configuration file (alternative to interactive wizard)",
)
def init(output: str, config: str) -> None:
    """Initialize a new WordPress deployment project.
    
    Use interactive wizard (default) or provide a config file with --config.
    """
    console.print("[bold cyan]WordPress Ansible CLI[/bold cyan]", style="bold")
    console.print(f"Version {__version__}\n")

    # Load config from file or run wizard
    if config:
        from .config import ConfigLoader
        console.print(f"[cyan]Loading configuration from: {config}[/cyan]\n")
        try:
            project_config = ConfigLoader.load(config)
        except Exception as e:
            console.print(f"[bold red]Error loading config: {e}[/bold red]")
            sys.exit(1)
    else:
        # Run interactive wizard
        project_config = run_wizard()
        
        if not project_config:
            console.print("[yellow]Setup cancelled.[/yellow]")
            sys.exit(0)

    # Generate project
    try:
        generator = ProjectGenerator(project_config, output)
        generator.generate()
    except Exception as e:
        console.print(f"[bold red]Error generating project: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--output",
    "-o",
    default="wpcli-config.example.json",
    help="Output path for config template",
)
def config_template(output: str) -> None:
    """Generate a configuration file template (JSON format)."""
    from .config import ConfigLoader
    
    try:
        ConfigLoader.create_template(output)
        console.print(f"\n[bold]Next steps:[/bold]")
        console.print(f"1. Copy and customize: [cyan]cp {output} my-config.json[/cyan]")
        console.print(f"2. Edit your config: [cyan]nano my-config.json[/cyan]")
        console.print(f"3. Generate project: [cyan]wpcli init --config my-config.json[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Error creating template: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.argument("project_dir", type=click.Path(exists=True))
def validate(project_dir: str) -> None:
    """Validate an existing Ansible project."""
    import subprocess

    project_path = Path(project_dir)
    site_yml = project_path / "site.yml"

    if not site_yml.exists():
        console.print(f"[red]Error: site.yml not found in {project_dir}[/red]")
        sys.exit(1)

    console.print(f"[cyan]Validating Ansible project: {project_dir}[/cyan]\n")

    # Syntax check
    console.print("[yellow]Running syntax check...[/yellow]")
    result = subprocess.run(
        ["ansible-playbook", str(site_yml), "--syntax-check"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print("[green]✓ Syntax check passed[/green]")
    else:
        console.print(f"[red]✗ Syntax check failed:\n{result.stderr}[/red]")
        sys.exit(1)

    console.print("\n[bold green]✓ Validation complete[/bold green]")


@cli.command()
@click.argument("secrets_file", type=click.Path(exists=True))
def encrypt(secrets_file: str) -> None:
    """Encrypt secrets file with Ansible Vault."""
    import subprocess

    console.print(f"[cyan]Encrypting {secrets_file} with Ansible Vault...[/cyan]\n")

    result = subprocess.run(
        ["ansible-vault", "encrypt", secrets_file],
        capture_output=False,
    )

    if result.returncode == 0:
        console.print(f"\n[green]✓ {secrets_file} encrypted successfully[/green]")
    else:
        console.print(f"[red]✗ Encryption failed[/red]")
        sys.exit(1)


@cli.command()
def info() -> None:
    """Display information about wpcli."""
    from rich.panel import Panel
    from rich.table import Table

    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Version", __version__)
    table.add_row("Python", f"{sys.version_info.major}.{sys.version_info.minor}")
    table.add_row("Description", "Production-ready WordPress deployment tool")

    panel = Panel(
        table,
        title="[bold cyan]WordPress Ansible CLI[/bold cyan]",
        border_style="cyan",
    )

    console.print(panel)
    console.print("\n[bold]Commands:[/bold]")
    console.print("  [cyan]wpcli init[/cyan]              - Interactive wizard")
    console.print("  [cyan]wpcli init --config FILE[/cyan] - Use config file")
    console.print("  [cyan]wpcli config-template[/cyan]   - Generate config template")
    console.print("  [cyan]wpcli validate PROJECT[/cyan]  - Validate Ansible project")
    console.print("  [cyan]wpcli encrypt FILE[/cyan]      - Encrypt with Ansible Vault")


if __name__ == "__main__":
    cli()
