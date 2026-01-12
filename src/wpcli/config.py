"""Configuration file handling."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console

console = Console()


class ConfigLoader:
    """Load and validate configuration from JSON files."""
    
    REQUIRED_FIELDS = [
        "server_ip",
        "ssh_user",
        "ssh_key",
        "domain",
        "site_title",
        "admin_email",
        "wordpress_version",
        "php_version",
        "db_mode",
        "db_engine",
        "db_host",
        "db_name",
        "db_user",
        "db_password",
        "environment",
    ]
    
    OPTIONAL_FIELDS = {
        "enable_ssl": True,
        "ssl_email": None,  # Will default to admin_email
        "enable_redis": True,
        "enable_monitoring": True,
        "enable_backups": True,
        "enable_security": True,
        "wp_admin_password": None,  # Will be auto-generated if not provided
        "wordpress_salts": None,  # Will be auto-generated if not provided
    }
    
    @staticmethod
    def load(config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        path = Path(config_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, 'r') as f:
            config = json.load(f)
        
        # Validate required fields
        missing = [field for field in ConfigLoader.REQUIRED_FIELDS if field not in config]
        if missing:
            raise ValueError(f"Missing required fields in config: {', '.join(missing)}")
        
        # Add optional fields with defaults
        for field, default in ConfigLoader.OPTIONAL_FIELDS.items():
            if field not in config:
                config[field] = default
        
        # Auto-generate if not provided
        if not config.get("wp_admin_password"):
            from .wizard import generate_password
            config["wp_admin_password"] = generate_password()
            console.print(f"[yellow]Generated admin password: {config['wp_admin_password']}[/yellow]")
        
        if not config.get("wordpress_salts"):
            from .wizard import generate_salt
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
            console.print("[green]✓ Generated WordPress salts[/green]")
        
        # Default ssl_email to admin_email if not provided
        if config.get("enable_ssl") and not config.get("ssl_email"):
            config["ssl_email"] = config["admin_email"]
        
        return config
    
    @staticmethod
    def create_template(output_path: str = "wpcli-config.example.json") -> None:
        """Create a template configuration file."""
        template = {
            "_comment": "WordPress Ansible CLI Configuration - Copy and customize for your deployment",
            
            "server_ip": "192.168.1.100",
            "ssh_user": "ubuntu",
            "ssh_key": "~/.ssh/id_rsa",
            
            "domain": "example.com",
            "site_title": "My WordPress Site",
            "admin_email": "admin@example.com",
            
            "wordpress_version": "6.4.2",
            "php_version": "8.2",
            
            "_db_comment": "Database: db_mode can be 'rds' or 'local', db_engine can be 'mysql', 'mariadb', or 'postgres'",
            "db_mode": "rds",
            "db_engine": "mysql",
            "db_host": "mydb.xxx.us-east-1.rds.amazonaws.com",
            "db_name": "wordpress_db",
            "db_user": "wpuser",
            "db_password": "YourSecurePassword123!",
            
            "_env_comment": "Environment: production, staging, or development",
            "environment": "production",
            
            "_features_comment": "Features (optional - defaults shown)",
            "enable_ssl": True,
            "ssl_email": "admin@example.com",
            "enable_redis": True,
            "enable_monitoring": True,
            "enable_backups": True,
            "enable_security": True,
            
            "_optional_comment": "Optional: Auto-generated if not provided",
            "_wp_admin_password": "Uncomment and set: wp_admin_password",
            "_wordpress_salts": "Uncomment and set: wordpress_salts object with 8 keys"
        }
        
        with open(output_path, 'w') as f:
            json.dump(template, f, indent=2)
        
        console.print(f"[green]✓ Created config template: {output_path}[/green]")
