# WordPress Ansible CLI - Full Documentation

For complete documentation, see:

- **Quick Start**: [README.md](README.md)
- **Config Files**: [CONFIG_GUIDE.md](docs/CONFIG_GUIDE.md)
- **Installation**: Run `pip install -e .`
- **Usage**: Run `wpcli --help`

## Commands

- `wpcli init` - Interactive wizard
- `wpcli init --config FILE` - Use config file
- `wpcli config-template` - Generate config template
- `wpcli validate PROJECT` - Validate Ansible project
- `wpcli encrypt FILE` - Encrypt with Ansible Vault
- `wpcli info` - Show version info

## Requirements

- Python 3.10+
- Ansible 2.15+
- Target server: Ubuntu 20.04/22.04

## Architecture

The codebase follows SOLID principles:

- `cli.py` - CLI commands
- `wizard.py` - Interactive configuration
- `config.py` - JSON config loader
- `validators.py` - Input validation
- `generator.py` - Project orchestrator
- `file_generators.py` - Config file generators
- `roles.py` - Ansible role generators

Each component has a single responsibility and is easy to extend.
