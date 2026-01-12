"""Interactive configuration wizard."""

import secrets
import string
from typing import Any, Dict, Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

from .validators import (
    validate_ip,
    validate_domain,
    validate_email,
    validate_ssh_key_path,
    validate_db_name,
    validate_db_user,
    validate_non_empty,
    validate_php_version,
    validate_wordpress_version,
)

console = Console()


def generate_password(length: int = 20) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_salt() -> str:
    """Generate a WordPress salt string."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_ []{}<>~`+=,.;:/?|"
    return "".join(secrets.choice(chars) for _ in range(64))


def get_validated_input(
    prompt_text: str,
    validator: callable,
    default: Optional[str] = None,
    is_password: bool = False,
) -> str:
    """Get and validate user input."""
    while True:
        if default:
            value = Prompt.ask(prompt_text, default=default, password=is_password)
        else:
            value = Prompt.ask(prompt_text, password=is_password)

        is_valid, result = validator(value)
        if is_valid:
            return result
        console.print(f"[red]✗ {result}[/red]")


def run_wizard() -> Dict[str, Any]:
    """Run the interactive configuration wizard."""
    console.print(
        Panel.fit(
            "[bold cyan]WordPress Ansible CLI - Configuration Wizard[/bold cyan]\n"
            "This wizard will guide you through configuring your WordPress deployment.",
            border_style="cyan",
        )
    )

    config: Dict[str, Any] = {}

    # Server Details
    console.print("\n[bold yellow]═══ Server Configuration ═══[/bold yellow]")
    config["server_ip"] = get_validated_input(
        "Target Server IP Address", lambda x: validate_ip(x)
    )
    config["ssh_user"] = get_validated_input(
        "SSH User", lambda x: validate_non_empty(x, "SSH User"), default="ubuntu"
    )
    config["ssh_key"] = get_validated_input(
        "Path to SSH Private Key",
        validate_ssh_key_path,
        default="~/.ssh/id_rsa",
    )

    # Site Details
    console.print("\n[bold yellow]═══ Site Configuration ═══[/bold yellow]")
    config["domain"] = get_validated_input("Domain Name (e.g., example.com)", validate_domain)
    config["site_title"] = get_validated_input(
        "Site Title",
        lambda x: validate_non_empty(x, "Site Title"),
        default="My WordPress Site",
    )
    config["admin_email"] = get_validated_input(
        "Admin Email", validate_email, default=f"admin@{config['domain']}"
    )

    # WordPress Configuration
    console.print("\n[bold yellow]═══ WordPress Configuration ═══[/bold yellow]")
    config["wordpress_version"] = get_validated_input(
        "WordPress Version", validate_wordpress_version, default="6.4.2"
    )
    config["php_version"] = get_validated_input(
        "PHP Version (8.1, 8.2, 8.3)", validate_php_version, default="8.2"
    )

    # Database Configuration - RDS FIRST PRIORITY
    console.print("\n[bold yellow]═══ Database Configuration ═══[/bold yellow]")
    console.print("[cyan]Choose your database setup:[/cyan]")
    console.print("  1. [bold]AWS RDS[/bold] (Recommended for production)")
    console.print("  2. Local MySQL")
    console.print("  3. Local MariaDB")

    db_choice = Prompt.ask(
        "Database Type", choices=["1", "2", "3"], default="1"
    )

    if db_choice == "1":
        config["db_mode"] = "rds"
        config["db_host"] = get_validated_input(
            "RDS Endpoint (e.g., mydb.xxx.us-east-1.rds.amazonaws.com)",
            lambda x: validate_non_empty(x, "RDS Endpoint"),
        )
        config["db_engine"] = Prompt.ask(
            "RDS Engine", choices=["mysql", "postgres"], default="mysql"
        )
    elif db_choice == "2":
        config["db_mode"] = "local"
        config["db_engine"] = "mysql"
        config["db_host"] = "localhost"
    else:
        config["db_mode"] = "local"
        config["db_engine"] = "mariadb"
        config["db_host"] = "localhost"

    config["db_name"] = get_validated_input(
        "Database Name", validate_db_name, default="wordpress_db"
    )
    config["db_user"] = get_validated_input(
        "Database Username", validate_db_user, default="wpuser"
    )
    config["db_password"] = get_validated_input(
        "Database Password",
        lambda x: validate_non_empty(x, "Database Password"),
        is_password=True,
    )

    # Environment
    console.print("\n[bold yellow]═══ Environment ═══[/bold yellow]")
    config["environment"] = Prompt.ask(
        "Environment", choices=["production", "staging", "development"], default="production"
    )

    # Features
    console.print("\n[bold yellow]═══ Features ═══[/bold yellow]")
    config["enable_ssl"] = Confirm.ask("Enable SSL/TLS with Let's Encrypt?", default=True)
    if config["enable_ssl"]:
        config["ssl_email"] = get_validated_input(
            "SSL Certificate Email", validate_email, default=config["admin_email"]
        )

    config["enable_redis"] = Confirm.ask("Enable Redis caching?", default=True)
    config["enable_monitoring"] = Confirm.ask("Enable monitoring tools?", default=True)
    config["enable_backups"] = Confirm.ask("Enable automated backups?", default=True)
    config["enable_security"] = Confirm.ask("Enable security hardening (Fail2Ban)?", default=True)

    # Generate secure credentials
    console.print("\n[bold yellow]═══ Generating Secure Credentials ═══[/bold yellow]")
    config["wp_admin_password"] = generate_password()
    config["wordpress_salts"] = {
        "auth_key": generate_salt(),
        "secure_auth_key": generate_salt(),
        "logged_in_key": generate_salt(),
        "nonce_key": generate_salt(),
        "auth_salt": generate_salt(),
        "secure_auth_salt": generate_salt(),
        "logged_in_salt": generate_salt(),
        "nonce_salt": generate_salt(),
    }

    console.print(f"[green]✓ Generated WordPress Admin Password: [bold]{config['wp_admin_password']}[/bold][/green]")
    console.print("[dim]This will be saved in vars/secrets.yml (encrypted)[/dim]")

    # Summary
    console.print("\n[bold yellow]═══ Configuration Summary ═══[/bold yellow]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Server IP", config["server_ip"])
    table.add_row("Domain", config["domain"])
    table.add_row("Database Mode", config["db_mode"].upper())
    table.add_row("Database Engine", config["db_engine"])
    table.add_row("Database Host", config["db_host"])
    table.add_row("Environment", config["environment"])
    table.add_row("PHP Version", config["php_version"])
    table.add_row("WordPress Version", config["wordpress_version"])
    table.add_row("SSL Enabled", "✓" if config["enable_ssl"] else "✗")
    table.add_row("Redis Enabled", "✓" if config["enable_redis"] else "✗")

    console.print(table)

    if not Confirm.ask("\n[bold]Proceed with this configuration?[/bold]", default=True):
        console.print("[yellow]Configuration cancelled.[/yellow]")
        return {}

    return config
