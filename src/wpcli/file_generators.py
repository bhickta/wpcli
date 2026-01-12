"""File generators for Ansible configuration files."""

from pathlib import Path
from typing import Dict, Any
import yaml


class FileGenerator:
    """Base class for file generators."""
    
    def __init__(self, output_dir: Path, config: Dict[str, Any]):
        self.output_dir = output_dir
        self.config = config
    
    def _write_file(self, path: Path, content: str) -> None:
        """Write content to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    
    def generate(self) -> None:
        """Generate the file. Must be implemented by subclasses."""
        raise NotImplementedError


class AnsibleCfgGenerator(FileGenerator):
    """Generate ansible.cfg file."""
    
    def generate(self) -> None:
        content = """[defaults]
inventory = inventory/hosts
host_key_checking = False
retry_files_enabled = False
roles_path = roles
gathering = smart
timeout = 30
forks = 5

[ssh_connection]
pipelining = True
ssh_args = -o ControlMaster=auto -o ControlPersist=60s

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
"""
        self._write_file(self.output_dir / "ansible.cfg", content)


class InventoryGenerator(FileGenerator):
    """Generate inventory/hosts file."""
    
    def generate(self) -> None:
        content = f"""[wordpress_servers]
{self.config['server_ip']} ansible_user={self.config['ssh_user']} ansible_ssh_private_key_file={self.config['ssh_key']}

[wordpress_servers:vars]
ansible_python_interpreter=/usr/bin/python3
deployment_env={self.config['environment']}

[{self.config['environment']}]
{self.config['server_ip']}
"""
        self._write_file(self.output_dir / "inventory" / "hosts", content)


class VarsGenerator(FileGenerator):
    """Generate vars/main.yml and vars/secrets.yml files."""
    
    def generate(self) -> None:
        # Main variables
        main_vars = {
            "wordpress_sites": [
                {
                    "domain": self.config["domain"],
                    "wordpress_version": self.config["wordpress_version"],
                    "site_title": self.config["site_title"],
                    "admin_user": "admin",
                    "admin_email": self.config["admin_email"],
                    "db_name": self.config["db_name"],
                    "db_user": self.config["db_user"],
                    "db_prefix": "wp_",
                    "php_version": self.config["php_version"],
                    "max_upload_size": "64M",
                    "memory_limit": "256M",
                    "enable_cache": self.config["enable_redis"],
                    "enable_ssl": self.config["enable_ssl"],
                    "ssl_email": self.config.get("ssl_email", self.config["admin_email"]),
                }
            ],
            "server_user": "www-data",
            "server_group": "www-data",
            "web_root": "/var/www",
            "nginx_http_port": 80,
            "nginx_https_port": 443,
            "php_version": self.config["php_version"],
            "php_max_execution_time": 180,
            "db_host": self.config["db_host"],
            "db_port": 3306,
            "db_charset": "utf8mb4",
            "db_collate": "utf8mb4_unicode_ci",
            "db_mode": self.config["db_mode"],
            "db_engine": self.config["db_engine"],
            "enable_redis": self.config["enable_redis"],
            "redis_host": "127.0.0.1",
            "redis_port": 6379,
            "enable_monitoring": self.config["enable_monitoring"],
            "enable_backups": self.config["enable_backups"],
            "enable_security": self.config["enable_security"],
            "deployment_env": self.config["environment"],
        }

        self._write_file(
            self.output_dir / "vars" / "main.yml",
            "---\n" + yaml.dump(main_vars, default_flow_style=False, sort_keys=False),
        )

        # Secrets
        secrets = {
            "db_password": self.config["db_password"],
            "wordpress_admin_password": self.config["wp_admin_password"],
            **self.config["wordpress_salts"],
        }

        self._write_file(
            self.output_dir / "vars" / "secrets.yml",
            "---\n" + yaml.dump(secrets, default_flow_style=False, sort_keys=False),
        )


class PlaybookGenerator(FileGenerator):
    """Generate site.yml playbook."""
    
    def generate(self) -> None:
        content = """---
- name: Deploy WordPress
  hosts: wordpress_servers
  become: yes
  vars_files:
    - vars/main.yml
    - vars/secrets.yml
  
  pre_tasks:
    - name: Update apt cache
      apt:
        update_cache: yes
        cache_valid_time: 3600
      when: ansible_os_family == "Debian"
    
    - name: Check disk space
      shell: df -h / | tail -1 | awk '{print $5}' | sed 's/%//'
      register: disk_usage
      changed_when: false
    
    - name: Fail if disk usage is too high
      fail:
        msg: "Disk usage is {{ disk_usage.stdout }}% - need at least 20% free"
      when: disk_usage.stdout | int > 80

  roles:
    - role: prerequisites
    - role: database
      when: db_mode == "local"
    - role: php
    - role: nginx
    - role: wordpress
    - role: redis
      when: enable_redis | default(true)
    - role: ssl
      when: enable_ssl | default(true)
    - role: monitoring
      when: enable_monitoring | default(true)
    - role: backup
      when: enable_backups | default(true)
    - role: security
      when: enable_security | default(true)

  post_tasks:
    - name: Ensure services are running
      service:
        name: "{{ item }}"
        state: started
        enabled: yes
      loop:
        - nginx
        - "php{{ php_version }}-fpm"
    
    - name: Display WordPress admin credentials
      debug:
        msg:
          - "WordPress Admin URL: https://{{ wordpress_sites[0].domain }}/wp-admin"
          - "Username: admin"
          - "Password: {{ wordpress_admin_password }}"
"""
        self._write_file(self.output_dir / "site.yml", content)


class HandlersGenerator(FileGenerator):
    """Generate handlers/main.yml file."""
    
    def generate(self) -> None:
        handlers = """---
- name: restart nginx
  service:
    name: nginx
    state: restarted

- name: reload nginx
  service:
    name: nginx
    state: reloaded

- name: restart php-fpm
  service:
    name: "php{{ php_version }}-fpm"
    state: restarted
"""
        self._write_file(self.output_dir / "handlers" / "main.yml", handlers)


class RequirementsGenerator(FileGenerator):
    """Generate requirements.yml for Ansible collections."""
    
    def generate(self) -> None:
        content = """---
collections:
  - name: community.general
    version: ">=8.0.0"
  - name: community.mysql
    version: ">=3.0.0"
"""
        self._write_file(self.output_dir / "requirements.yml", content)


class ReadmeGenerator(FileGenerator):
    """Generate project README.md file."""
    
    def generate(self) -> None:
        readme = f"""# WordPress Ansible Deployment

Production-ready WordPress deployment for **{self.config['domain']}**

## Configuration Summary

- **Domain**: {self.config['domain']}
- **Environment**: {self.config['environment']}
- **Database**: {self.config['db_mode'].upper()} ({self.config['db_engine']})
- **PHP Version**: {self.config['php_version']}
- **WordPress Version**: {self.config['wordpress_version']}
- **SSL**: {'Enabled' if self.config['enable_ssl'] else 'Disabled'}
- **Redis Cache**: {'Enabled' if self.config['enable_redis'] else 'Disabled'}

## Prerequisites

1. **Ansible installed** on your local machine:
   ```bash
   pip install ansible
   ```

2. **Install Ansible collections**:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

3. **SSH access** to target server ({self.config['server_ip']})

4. **Domain DNS** pointing to server IP (required for SSL)

## Deployment

### 1. Install Collections

```bash
ansible-galaxy collection install -r requirements.yml
```

### 2. Review Configuration

Check the generated files:
- `vars/main.yml` - Main configuration
- `vars/secrets.yml` - Encrypted secrets (use `ansible-vault view vars/secrets.yml`)

### 3. Run Deployment

```bash
ansible-playbook site.yml
```

If you encrypted secrets with Ansible Vault:
```bash
ansible-playbook site.yml --ask-vault-pass
```

### 4. Access WordPress

After successful deployment:
- **URL**: https://{self.config['domain']}/wp-admin
- **Username**: admin
- **Password**: Check `vars/secrets.yml` (wordpress_admin_password)

## Ansible Vault

Secrets are stored in `vars/secrets.yml`. To encrypt:

```bash
ansible-vault encrypt vars/secrets.yml
```

To view encrypted secrets:
```bash
ansible-vault view vars/secrets.yml
```

To edit encrypted secrets:
```bash
ansible-vault edit vars/secrets.yml
```

## Maintenance

### Update WordPress
```bash
ansible-playbook site.yml --tags wordpress
```

### Backup Database
Automatic backups run daily at 2 AM. Manual backup:
```bash
ssh {self.config['ssh_user']}@{self.config['server_ip']} /usr/local/bin/backup-wordpress-db.sh
```

### View Logs
```bash
# Nginx logs
ssh {self.config['ssh_user']}@{self.config['server_ip']} tail -f /var/log/nginx/access.log

# PHP-FPM logs
ssh {self.config['ssh_user']}@{self.config['server_ip']} tail -f /var/log/php{self.config['php_version']}-fpm.log
```

## Troubleshooting

### SSL Certificate Issues
Ensure:
- Domain DNS points to server IP
- Ports 80 and 443 are open
- Run: `ansible-playbook site.yml --tags ssl`

### Database Connection Issues
For RDS:
- Verify security group allows connections from server IP
- Check RDS endpoint and credentials

For local database:
- Check MySQL/MariaDB service: `systemctl status mysql`

### Performance Issues
- Check Redis: `redis-cli ping`
- Monitor PHP-FPM: `systemctl status php{self.config['php_version']}-fpm`
- Review server resources: `htop`

## Security

- Fail2Ban monitors and blocks brute force attempts
- Automatic security updates enabled
- WordPress file editing disabled
- Strong passwords auto-generated

## Support

Generated by wpcli v1.0.0
"""
        self._write_file(self.output_dir / "README.md", readme)
