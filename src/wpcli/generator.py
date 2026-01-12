"""Refactored project generation engine following SOLID and DRY principles."""

from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .roles import ROLE_GENERATORS
from .file_generators import (
    AnsibleCfgGenerator,
    InventoryGenerator,
    VarsGenerator,
    PlaybookGenerator,
    HandlersGenerator,
    RequirementsGenerator,
    ReadmeGenerator,
)

console = Console()


class DirectoryStructure:
    """Handles creation of directory structure."""
    
    ROLE_NAMES = [
        "prerequisites",
        "database",
        "nginx",
        "php",
        "wordpress",
        "ssl",
        "redis",
        "monitoring",
        "backup",
        "security",
    ]
    
    ROLE_SUBDIRS = ["tasks", "templates", "handlers", "defaults"]
    
    @staticmethod
    def create(output_dir: Path) -> None:
        """Create complete directory structure."""
        dirs = [
            output_dir,
            output_dir / "inventory",
            output_dir / "vars",
            output_dir / "roles",
            output_dir / "handlers",
        ]

        # Create role directories
        for role in DirectoryStructure.ROLE_NAMES:
            for subdir in DirectoryStructure.ROLE_SUBDIRS:
                dirs.append(output_dir / "roles" / role / subdir)

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

            # Generate roles
            progress.update(task, description="Generating roles...")
            self._generate_roles()

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
            RequirementsGenerator(self.output_dir, self.config),
            ReadmeGenerator(self.output_dir, self.config),
        ]
        
        for generator in generators:
            generator.generate()

    def _generate_roles(self) -> None:
        """Generate all Ansible roles using simplified functions."""
        from .roles import generate_all_roles
        generate_all_roles(self.output_dir, self.config)

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
