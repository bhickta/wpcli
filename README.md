# WordPress Ansible CLI

Production-ready WordPress deployment tool using Python and Ansible.

## Quick Start

```bash
# Install
pip install -e .

# Interactive wizard
wpcli init

# Or use config file
wpcli config-template
cp wpcli-config.example.json my-config.json
# Edit my-config.json
wpcli init --config my-config.json

# Deploy
cd wordpress-ansible
ansible-galaxy collection install -r requirements.yml
ansible-playbook site.yml
```

## Features

- 🚀 Interactive CLI wizard or JSON config file
- 🗄️ AWS RDS, MySQL, or MariaDB support
- 🔒 Security hardening (Fail2Ban, SSL, firewall)
- ⚡ Performance optimization (Redis, OPcache)
- 📊 Monitoring and health checks
- 💾 Automated backups
- 🎯 Multi-environment support

## Documentation

- [README.md](README.md) - Full documentation
- [CONFIG_GUIDE.md](docs/CONFIG_GUIDE.md) - Config file guide

## License

MIT
