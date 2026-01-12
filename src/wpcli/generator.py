"""Refactored project generation engine following SOLID and DRY principles."""

from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .file_generators import (
    AnsibleCfgGenerator,
    InventoryGenerator,
    VarsGenerator,
    PlaybookGenerator,
    HandlersGenerator,
    TemplateGenerator,
    RequirementsGenerator,
    ReadmeGenerator,
)

console = Console()


class DirectoryStructure:
    """Handles creation of directory structure."""
    
    @staticmethod
    def create(output_dir: Path) -> None:
        """Create complete directory structure."""
        dirs = [
            output_dir,
            output_dir / "inventory",
            output_dir / "vars",
            output_dir / "templates",
            output_dir / "handlers",
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)


class ProjectGenerator:
    """
    Generate Ansible project structure from configuration.
    
    Follows SOLID principles:
    - Single Responsibility: Orchestrates generation, delegates to specialized generators
    - Open/Closed: Easy to add new generators without modifying this class
    - Liskov Substitution: All generators follow same interface
    - Interface Segregation: Generators only implement what they need
    - Dependency Inversion: Depends on abstractions (generator classes), not concrete implementations
    """

    def __init__(self, config: Dict[str, Any], output_dir: str = "wordpress-ansible"):
        self.config = config
        self.output_dir = Path(output_dir)

    def generate(self) -> None:
        """Generate the complete project structure."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating project...", total=None)

            # Create directory structure
            progress.update(task, description="Creating directory structure...")
            DirectoryStructure.create(self.output_dir)

            # Generate configuration files
            progress.update(task, description="Generating Ansible configuration...")
            self._generate_config_files()

            # Final steps
            progress.update(task, description="Finalizing project...")
            self._print_vault_instructions()

        console.print(f"\n[bold green]✓ Project generated successfully: {self.output_dir}[/bold green]")
        self._print_next_steps()

    def _generate_config_files(self) -> None:
        """Generate all configuration files using dedicated generators."""
        generators = [
            AnsibleCfgGenerator(self.output_dir, self.config),
            InventoryGenerator(self.output_dir, self.config),
            VarsGenerator(self.output_dir, self.config),
            PlaybookGenerator(self.output_dir, self.config),
            HandlersGenerator(self.output_dir, self.config),
            TemplateGenerator(self.output_dir, self.config),
            RequirementsGenerator(self.output_dir, self.config),
            ReadmeGenerator(self.output_dir, self.config),
        ]
        
        for generator in generators:
            generator.generate()

    def _print_vault_instructions(self) -> None:
        """Print instructions for Ansible Vault encryption."""
        secrets_file = self.output_dir / "vars" / "secrets.yml"
        
        console.print("\n[yellow]Would you like to encrypt secrets with Ansible Vault?[/yellow]")
        console.print("[dim]This is recommended for production deployments.[/dim]")
        console.print(f"\n[cyan]To encrypt secrets later, run:[/cyan]")
        console.print(f"[bold]ansible-vault encrypt {secrets_file}[/bold]")

    def _print_next_steps(self) -> None:
        """Print next steps for the user."""
        console.print("\n[bold cyan]═══ Next Steps ═══[/bold cyan]")
        console.print(f"1. [bold]cd {self.output_dir}[/bold]")
        console.print("2. [bold]ansible-galaxy collection install -r requirements.yml[/bold]")
        console.print("3. [bold]ansible-playbook site.yml[/bold]")
        console.print(f"\n[dim]See {self.output_dir}/README.md for detailed instructions[/dim]")
