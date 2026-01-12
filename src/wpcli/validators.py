"""Input validation utilities."""

import re
import ipaddress
from pathlib import Path
from typing import Optional
import validators


def validate_ip(ip: str) -> tuple[bool, str]:
    """Validate IP address."""
    try:
        ipaddress.ip_address(ip)
        return True, ip
    except ValueError:
        return False, "Invalid IP address format"


def validate_domain(domain: str) -> tuple[bool, str]:
    """Validate domain name."""
    if validators.domain(domain):
        return True, domain
    return False, "Invalid domain name format"


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email address."""
    if validators.email(email):
        return True, email
    return False, "Invalid email address format"


def validate_ssh_key_path(path: str) -> tuple[bool, str]:
    """Validate SSH key file exists."""
    expanded = Path(path).expanduser()
    if expanded.exists() and expanded.is_file():
        return True, str(expanded)
    return False, f"SSH key file not found: {path}"


def validate_db_name(name: str) -> tuple[bool, str]:
    """Validate database name (alphanumeric and underscores only)."""
    if re.match(r"^[a-zA-Z0-9_]+$", name) and len(name) <= 64:
        return True, name
    return False, "Database name must be alphanumeric with underscores, max 64 characters"


def validate_db_user(user: str) -> tuple[bool, str]:
    """Validate database username."""
    if re.match(r"^[a-zA-Z0-9_]+$", user) and len(user) <= 32:
        return True, user
    return False, "Database user must be alphanumeric with underscores, max 32 characters"


def validate_non_empty(value: str, field_name: str) -> tuple[bool, str]:
    """Validate non-empty string."""
    if value and value.strip():
        return True, value.strip()
    return False, f"{field_name} cannot be empty"


def validate_port(port: str) -> tuple[bool, int]:
    """Validate port number."""
    try:
        port_num = int(port)
        if 1 <= port_num <= 65535:
            return True, port_num
        return False, "Port must be between 1 and 65535"
    except ValueError:
        return False, "Port must be a number"


def validate_php_version(version: str) -> tuple[bool, str]:
    """Validate PHP version."""
    valid_versions = ["8.1", "8.2", "8.3"]
    if version in valid_versions:
        return True, version
    return False, f"PHP version must be one of: {', '.join(valid_versions)}"


def validate_wordpress_version(version: str) -> tuple[bool, str]:
    """Validate WordPress version format."""
    if re.match(r"^\d+\.\d+(\.\d+)?$", version):
        return True, version
    return False, "WordPress version must be in format X.Y or X.Y.Z"
