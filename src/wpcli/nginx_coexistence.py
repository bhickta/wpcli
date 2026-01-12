"""Nginx coexistence detector and handler."""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console

console = Console()


class NginxCoexistence:
    """Detect and handle existing Nginx installations."""
    
    @staticmethod
    def is_nginx_running() -> bool:
        """Check if Nginx is already running."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "nginx"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def get_listening_ports() -> Dict[int, str]:
        """Get ports that Nginx is listening on."""
        try:
            result = subprocess.run(
                ["sudo", "netstat", "-tlnp"],
                capture_output=True,
                text=True
            )
            
            ports = {}
            for line in result.stdout.split('\n'):
                if 'nginx' in line.lower():
                    parts = line.split()
                    if len(parts) >= 4:
                        addr = parts[3]
                        if ':' in addr:
                            port = int(addr.split(':')[-1])
                            ports[port] = line
            
            return ports
        except:
            return {}
    
    @staticmethod
    def get_existing_sites() -> list:
        """Get list of existing Nginx site configs."""
        sites_enabled = Path("/etc/nginx/sites-enabled")
        if sites_enabled.exists():
            return [f.name for f in sites_enabled.iterdir() if f.is_symlink() or f.is_file()]
        return []
    
    @staticmethod
    def detect_coexistence_mode() -> Optional[Dict[str, Any]]:
        """Detect if we need coexistence mode."""
        if not NginxCoexistence.is_nginx_running():
            return None
        
        ports = NginxCoexistence.get_listening_ports()
        sites = NginxCoexistence.get_existing_sites()
        
        if 80 in ports or 443 in ports:
            return {
                "nginx_running": True,
                "ports_in_use": list(ports.keys()),
                "existing_sites": sites,
                "mode": "coexistence"
            }
        
        return None
    
    @staticmethod
    def prompt_coexistence_strategy(existing_info: Dict[str, Any]) -> str:
        """Prompt user for coexistence strategy."""
        from rich.panel import Panel
        from rich.prompt import Prompt
        
        console.print("\n[yellow]⚠️  Existing Nginx Installation Detected[/yellow]")
        console.print(Panel(
            f"[cyan]Ports in use:[/cyan] {', '.join(map(str, existing_info['ports_in_use']))}\n"
            f"[cyan]Existing sites:[/cyan] {', '.join(existing_info['existing_sites']) if existing_info['existing_sites'] else 'None'}",
            title="Current Nginx Status",
            border_style="yellow"
        ))
        
        console.print("\n[bold]Deployment Options:[/bold]")
        console.print("  1. [cyan]Add WordPress to existing Nginx[/cyan] (Recommended - Safe)")
        console.print("     → WordPress gets its own site config")
        console.print("     → Existing sites remain untouched")
        console.print("  2. [yellow]Use different ports[/yellow] (WordPress on 8080/8443)")
        console.print("  3. [red]Overwrite Nginx config[/red] (⚠️  May break existing sites)")
        
        choice = Prompt.ask(
            "\nChoose deployment strategy",
            choices=["1", "2", "3"],
            default="1"
        )
        
        if choice == "1":
            return "coexist"
        elif choice == "2":
            return "different_ports"
        else:
            confirm = Prompt.ask(
                "[red]⚠️  This will overwrite Nginx configs. Continue?[/red]",
                choices=["yes", "no"],
                default="no"
            )
            return "overwrite" if confirm == "yes" else "coexist"
