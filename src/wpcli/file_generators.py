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
# roles_path = roles  <-- No longer needed
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
            "nginx_http_port": self.config.get("nginx_http_port", 80),
            "nginx_https_port": self.config.get("nginx_https_port", 443),
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
    """Generate site.yml playbook with all tasks."""
    
    def generate(self) -> None:
        # Check if coexistence mode
        use_coexistence = self.config.get("nginx_coexistence", False)
        
        # Define tasks blocks
        tasks_prerequisites = """
    # Prerequisites
    - name: Install system utilities
      apt:
        name:
          - curl
          - git
          - unzip
          - zip
          - acl
          - python3-pymysql
          - python3-psycopg2
          - mysql-client
          - ufw
          - ntp
        state: present
        update_cache: yes

    - name: Allow SSH through firewall
      command: ufw allow 22/tcp
      changed_when: false

    - name: Allow HTTP through firewall
      command: ufw allow 80/tcp
      changed_when: false

    - name: Allow HTTPS through firewall
      command: ufw allow 443/tcp
      changed_when: false

    - name: Enable UFW
      command: ufw --force enable
      changed_when: false

    - name: Start and enable NTP
      service:
        name: ntp
        state: started
        enabled: yes
"""

        tasks_database = """
    # Database
    - block:
        - name: Install {{ db_engine|upper }}
          apt:
            name:
              - "{{ 'mariadb-server' if db_engine == 'mariadb' else 'mysql-server' }}"
              - "{{ 'mariadb-client' if db_engine == 'mariadb' else 'mysql-client' }}"
            state: present

        - name: Start and enable {{ db_engine|upper }}
          service:
            name: "{{ 'mariadb' if db_engine == 'mariadb' else 'mysql' }}"
            state: started
            enabled: yes

        - name: Set root password
          community.mysql.mysql_user:
            name: root
            password: "{{ db_password }}"
            login_unix_socket: /var/run/mysqld/mysqld.sock
            state: present
          ignore_errors: yes

        - name: Remove anonymous users
          community.mysql.mysql_user:
            name: ''
            host_all: yes
            state: absent
            login_user: root
            login_password: "{{ db_password }}"

        - name: Remove test database
          community.mysql.mysql_db:
            name: test
            state: absent
            login_user: root
            login_password: "{{ db_password }}"

        - name: Create WordPress database
          community.mysql.mysql_db:
            name: "{{ item.db_name }}"
            state: present
            encoding: utf8mb4
            collation: utf8mb4_unicode_ci
            login_user: root
            login_password: "{{ db_password }}"
          loop: "{{ wordpress_sites }}"

        - name: Create WordPress database user
          community.mysql.mysql_user:
            name: "{{ item.db_user }}"
            password: "{{ db_password }}"
            priv: "{{ item.db_name }}.*:ALL"
            state: present
            login_user: root
            login_password: "{{ db_password }}"
          loop: "{{ wordpress_sites }}"

        - name: Configure {{ db_engine|upper }} performance
          lineinfile:
            path: /etc/mysql/mysql.conf.d/mysqld.cnf
            line: "{{ item }}"
            insertafter: '^\\[mysqld\\]'
          loop:
            - "innodb_buffer_pool_size = 256M"
            - "max_connections = 200"
          notify: restart database
      when: db_mode == "local"
"""

        tasks_php = """
    # PHP
    - name: Add PHP repository
      apt_repository:
        repo: 'ppa:ondrej/php'
        state: present

    - name: Install PHP and extensions
      apt:
        name:
          - "php{{ php_version }}-fpm"
          - "php{{ php_version }}-cli"
          - "php{{ php_version }}-mysql"
          - "php{{ php_version }}-pgsql"
          - "php{{ php_version }}-xml"
          - "php{{ php_version }}-curl"
          - "php{{ php_version }}-gd"
          - "php{{ php_version }}-mbstring"
          - "php{{ php_version }}-zip"
          - "php{{ php_version }}-intl"
          - "php{{ php_version }}-redis"
          - "php{{ php_version }}-opcache"
        state: present
        update_cache: yes
      notify: restart php-fpm

    - name: Configure PHP-FPM pool
      lineinfile:
        path: "/etc/php/{{ php_version }}/fpm/pool.d/www.conf"
        regexp: "{{ item.regexp }}"
        line: "{{ item.line }}"
      loop:
        - { regexp: '^pm =', line: 'pm = dynamic' }
        - { regexp: '^pm.max_children =', line: 'pm.max_children = 50' }
        - { regexp: '^pm.start_servers =', line: 'pm.start_servers = 5' }
        - { regexp: '^pm.min_spare_servers =', line: 'pm.min_spare_servers = 5' }
        - { regexp: '^pm.max_spare_servers =', line: 'pm.max_spare_servers = 35' }
      notify: restart php-fpm

    - name: Configure PHP settings
      lineinfile:
        path: "/etc/php/{{ php_version }}/fpm/php.ini"
        regexp: "{{ item.regexp }}"
        line: "{{ item.line }}"
      loop:
        - { regexp: '^upload_max_filesize =', line: 'upload_max_filesize = 64M' }
        - { regexp: '^post_max_size =', line: 'post_max_size = 64M' }
        - { regexp: '^memory_limit =', line: 'memory_limit = 256M' }
        - { regexp: '^max_execution_time =', line: 'max_execution_time = 180' }
        - { regexp: '^;opcache.enable=', line: 'opcache.enable=1' }
        - { regexp: '^;opcache.memory_consumption=', line: 'opcache.memory_consumption=128' }
      notify: restart php-fpm
"""

        if use_coexistence:
            tasks_nginx = """
    # Nginx (Coexistence)
    - name: Check if Nginx is installed
      command: nginx -v
      register: nginx_check
      ignore_errors: yes
      changed_when: false

    - name: Install Nginx if not present
      apt:
        name: nginx
        state: present
      when: nginx_check.rc != 0

    - name: Create WordPress site config
      template:
        src: templates/wordpress.conf.j2
        dest: "/etc/nginx/sites-available/{{ item.domain }}"
      loop: "{{ wordpress_sites }}"
      notify: reload nginx

    - name: Enable WordPress site config
      file:
        src: "/etc/nginx/sites-available/{{ item.domain }}"
        dest: "/etc/nginx/sites-enabled/{{ item.domain }}"
        state: link
      loop: "{{ wordpress_sites }}"
      notify: reload nginx

    - name: Test Nginx configuration
      command: nginx -t
      register: nginx_test
      changed_when: false

    - name: Display Nginx test results
      debug:
        msg: "{{ nginx_test.stderr_lines }}"
"""
        else:
            tasks_nginx = """
    # Nginx
    - name: Install Nginx
      apt:
        name: nginx
        state: present

    - name: Remove default config
      file:
        path: /etc/nginx/sites-enabled/default
        state: absent
      notify: reload nginx

    - name: Create site config
      template:
        src: templates/wordpress.conf.j2
        dest: "/etc/nginx/sites-available/{{ item.domain }}"
      loop: "{{ wordpress_sites }}"
      notify: reload nginx

    - name: Enable site config
      file:
        src: "/etc/nginx/sites-available/{{ item.domain }}"
        dest: "/etc/nginx/sites-enabled/{{ item.domain }}"
        state: link
      loop: "{{ wordpress_sites }}"
      notify: reload nginx

    - name: Configure Nginx security headers
      blockinfile:
        path: /etc/nginx/nginx.conf
        marker: "# {mark} ANSIBLE MANAGED SECURITY HEADERS"
        insertafter: "http {"
        block: |
          # Security headers
          add_header X-Frame-Options "SAMEORIGIN" always;
          add_header X-Content-Type-Options "nosniff" always;
          add_header X-XSS-Protection "1; mode=block" always;
          add_header Referrer-Policy "no-referrer-when-downgrade" always;
          
          # Gzip compression
          gzip on;
          gzip_vary on;
          gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;
      notify: reload nginx
"""

        tasks_wordpress = """
    # WordPress
    - name: Create web root directory
      file:
        path: "{{ web_root }}/{{ item.domain }}"
        state: directory
        owner: "{{ server_user }}"
        group: "{{ server_group }}"
        mode: '0755'
      loop: "{{ wordpress_sites }}"

    - name: Download WordPress
      get_url:
        url: "https://wordpress.org/wordpress-{{ item.wordpress_version }}.tar.gz"
        dest: "/tmp/wordpress-{{ item.wordpress_version }}.tar.gz"
      loop: "{{ wordpress_sites }}"

    - name: Extract WordPress
      unarchive:
        src: "/tmp/wordpress-{{ item.wordpress_version }}.tar.gz"
        dest: "/tmp"
        remote_src: yes
      loop: "{{ wordpress_sites }}"

    - name: Copy WordPress files
      shell: "cp -rn /tmp/wordpress/* {{ web_root }}/{{ item.domain }}/"
      loop: "{{ wordpress_sites }}"
      args:
        creates: "{{ web_root }}/{{ item.domain }}/wp-config-sample.php"

    - name: Create wp-config.php
      template:
        src: templates/wp-config.php.j2
        dest: "{{ web_root }}/{{ item.domain }}/wp-config.php"
        owner: "{{ server_user }}"
        group: "{{ server_group }}"
        mode: '0640'
      loop: "{{ wordpress_sites }}"

    - name: Set WordPress permissions
      file:
        path: "{{ web_root }}/{{ item.domain }}"
        owner: "{{ server_user }}"
        group: "{{ server_group }}"
        recurse: yes
      loop: "{{ wordpress_sites }}"

    - name: Install WP-CLI
      get_url:
        url: https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
        dest: /usr/local/bin/wp
        mode: '0755'

    - name: Complete WordPress installation
      command: >
        wp core install
        --url="https://{{ item.domain }}"
        --title="{{ item.site_title }}"
        --admin_user="{{ item.admin_user }}"
        --admin_password="{{ wordpress_admin_password }}"
        --admin_email="{{ item.admin_email }}"
        --path="{{ web_root }}/{{ item.domain }}"
        --allow-root
      loop: "{{ wordpress_sites }}"
      args:
        creates: "{{ web_root }}/{{ item.domain }}/wp-content/uploads"
"""

        tasks_ssl = """
    # SSL
    - block:
        - name: Install Certbot
          apt:
            name:
              - certbot
              - python3-certbot-nginx
            state: present

        - name: Request SSL certificate
          command: >
            certbot --nginx
            -d {{ item.domain }}
            -d www.{{ item.domain }}
            --non-interactive
            --agree-tos
            --email {{ item.ssl_email }}
            --redirect
          args:
            creates: "/etc/letsencrypt/live/{{ item.domain }}/fullchain.pem"
          loop: "{{ wordpress_sites }}"

        - name: Set up auto-renewal
          cron:
            name: "Certbot renewal"
            minute: "0"
            hour: "3"
            job: "certbot renew --quiet --post-hook 'systemctl reload nginx'"
      when: enable_ssl | default(true)
"""

        tasks_redis = """
    # Redis
    - block:
        - name: Install Redis
          apt:
            name: redis-server
            state: present

        - name: Configure Redis
          lineinfile:
            path: /etc/redis/redis.conf
            regexp: "{{ item.regexp }}"
            line: "{{ item.line }}"
          loop:
            - { regexp: '^maxmemory ', line: 'maxmemory 256mb' }
            - { regexp: '^maxmemory-policy', line: 'maxmemory-policy allkeys-lru' }
          notify: restart redis

        - name: Start and enable Redis
          service:
            name: redis-server
            state: started
            enabled: yes

        - name: Install Redis object cache plugin
          command: >
            wp plugin install redis-cache --activate
            --path="{{ web_root }}/{{ item.domain }}"
            --allow-root
          loop: "{{ wordpress_sites }}"
          when: item.enable_cache

        - name: Enable Redis object cache
          command: >
            wp redis enable
            --path="{{ web_root }}/{{ item.domain }}"
            --allow-root
          loop: "{{ wordpress_sites }}"
          when: item.enable_cache
          ignore_errors: yes
      when: enable_redis | default(true)
"""

        tasks_monitoring = """
    # Monitoring
    - block:
        - name: Install monitoring tools
          apt:
            name:
              - htop
              - iotop
              - nethogs
              - sysstat
            state: present

        - name: Enable sysstat
          lineinfile:
            path: /etc/default/sysstat
            regexp: '^ENABLED='
            line: 'ENABLED="true"'

        - name: Start sysstat
          service:
            name: sysstat
            state: started
            enabled: yes
      when: enable_monitoring | default(true)
"""

        tasks_backup = """
    # Backups
    - block:
        - name: Create backup directory
          file:
            path: /var/backups/wordpress
            state: directory
            mode: '0700'

        - name: Create database backup script
          template:
            src: templates/backup-db.sh.j2
            dest: /usr/local/bin/backup-wordpress-db.sh
            mode: '0755'

        - name: Schedule database backups
          cron:
            name: "WordPress database backup"
            minute: "0"
            hour: "2"
            job: "/usr/local/bin/backup-wordpress-db.sh"
      when: enable_backups | default(true)
"""

        tasks_security = """
    # Security
    - block:
        - name: Install Fail2Ban
          apt:
            name: fail2ban
            state: present

        - name: Configure Fail2Ban for WordPress
          copy:
            dest: /etc/fail2ban/filter.d/wordpress.conf
            content: |
              [Definition]
              failregex = ^<HOST> .* "POST /wp-login.php
              ignoreregex =

        - name: Enable Fail2Ban WordPress jail
          copy:
            dest: /etc/fail2ban/jail.d/wordpress.conf
            content: |
              [wordpress]
              enabled = true
              port = http,https
              filter = wordpress
              logpath = /var/log/nginx/access.log
              maxretry = 3
              bantime = 3600
          notify: restart fail2ban

        - name: Start and enable Fail2Ban
          service:
            name: fail2ban
            state: started
            enabled: yes

        - name: Install unattended-upgrades
          apt:
            name: unattended-upgrades
            state: present

        - name: Enable automatic security updates
          copy:
            dest: /etc/apt/apt.conf.d/50unattended-upgrades
            content: |
              Unattended-Upgrade::Allowed-Origins {
                "${distro_id}:${distro_codename}-security";
              };
              Unattended-Upgrade::AutoFixInterruptedDpkg "true";
              Unattended-Upgrade::Remove-Unused-Dependencies "true";
      when: enable_security | default(true)
"""

        # Combine content
        content = f"""---
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
      shell: df -h / | tail -1 | awk '{{print $5}}' | sed 's/%//'
      register: disk_usage
      changed_when: false
    
    - name: Fail if disk usage is too high
      fail:
        msg: "Disk usage is {{{{ disk_usage.stdout }}}}% - need at least 20% free"
      when: disk_usage.stdout | int > 80

  tasks:
{tasks_prerequisites}
{tasks_database}
{tasks_php}
{tasks_nginx}
{tasks_wordpress}
{tasks_ssl}
{tasks_redis}
{tasks_monitoring}
{tasks_backup}
{tasks_security}

  handlers:
    - import_tasks: handlers/main.yml

  post_tasks:
    - name: Ensure services are running
      service:
        name: "{{{{ item }}}}"
        state: started
        enabled: yes
      loop:
        - nginx
        - "php{{{{ php_version }}}}-fpm"
    
    - name: Display WordPress admin credentials
      debug:
        msg:
          - "WordPress Admin URL: https://{{{{ wordpress_sites[0].domain }}}}/wp-admin"
          - "Username: admin"
          - "Password: {{{{ wordpress_admin_password }}}}"
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

- name: restart database
  service:
    name: "{{ 'mariadb' if db_engine|default('mysql') == 'mariadb' else 'mysql' }}"
    state: restarted

- name: restart redis
  service:
    name: redis-server
    state: restarted

- name: restart fail2ban
  service:
    name: fail2ban
    state: restarted
"""
        self._write_file(self.output_dir / "handlers" / "main.yml", handlers)


class TemplateGenerator(FileGenerator):
    """Generate all template files."""
    
    def generate(self) -> None:
        # Nginx configuration
        nginx_conf = """server {
    listen {{ nginx_http_port }};
    server_name {{ item.domain }} www.{{ item.domain }};
    root {{ web_root }}/{{ item.domain }};
    index index.php index.html;

    client_max_body_size {{ item.max_upload_size }};

    # Security
    location ~ /\\.ht {
        deny all;
    }
    
    location ~ /wp-config.php {
        deny all;
    }

    location / {
        try_files $uri $uri/ /index.php$is_args$args;
    }

    location ~ \\.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php{{ item.php_version }}-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
        fastcgi_read_timeout 180;
    }
    
    # Cache static assets
    location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires max;
        log_not_found off;
        access_log off;
    }
}
"""
        self._write_file(self.output_dir / "templates" / "wordpress.conf.j2", nginx_conf)

        # WordPress configuration
        wp_config = """<?php
define( 'DB_NAME', '{{ item.db_name }}' );
define( 'DB_USER', '{{ item.db_user }}' );
define( 'DB_PASSWORD', '{{ db_password }}' );
define( 'DB_HOST', '{{ db_host }}' );
define( 'DB_CHARSET', '{{ db_charset }}' );
define( 'DB_COLLATE', '{{ db_collate }}' );

{% if db_mode == 'rds' and db_engine == 'mysql' %}
define( 'MYSQL_CLIENT_FLAGS', MYSQLI_CLIENT_SSL );
{% endif %}

define( 'AUTH_KEY',         '{{ auth_key }}' );
define( 'SECURE_AUTH_KEY',  '{{ secure_auth_key }}' );
define( 'LOGGED_IN_KEY',    '{{ logged_in_key }}' );
define( 'NONCE_KEY',        '{{ nonce_key }}' );
define( 'AUTH_SALT',        '{{ auth_salt }}' );
define( 'SECURE_AUTH_SALT', '{{ secure_auth_salt }}' );
define( 'LOGGED_IN_SALT',   '{{ logged_in_salt }}' );
define( 'NONCE_SALT',       '{{ nonce_salt }}' );

$table_prefix = '{{ item.db_prefix }}';

{% if item.enable_cache %}
define( 'WP_REDIS_HOST', '{{ redis_host }}' );
define( 'WP_REDIS_PORT', {{ redis_port }} );
define( 'WP_CACHE', true );
{% endif %}

define( 'WP_DEBUG', {{ 'true' if deployment_env == 'development' else 'false' }} );
define( 'DISALLOW_FILE_EDIT', true );
define( 'FORCE_SSL_ADMIN', {{ 'true' if item.enable_ssl else 'false' }} );

if ( ! defined( 'ABSPATH' ) ) {
\tdefine( 'ABSPATH', __DIR__ . '/' );
}
require_once ABSPATH . 'wp-settings.php';
"""
        self._write_file(self.output_dir / "templates" / "wp-config.php.j2", wp_config)

        # Backup script
        backup_script = """#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
{% for site in wordpress_sites %}
mysqldump -h {{ db_host }} -u {{ site.db_user }} -p'{{ db_password }}' {{ site.db_name }} | gzip > /var/backups/wordpress/{{ site.domain }}_${DATE}.sql.gz
{% endfor %}
find /var/backups/wordpress -name "*.sql.gz" -mtime +7 -delete
"""
        self._write_file(self.output_dir / "templates" / "backup-db.sh.j2", backup_script)


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

## Configured Features
- **Environment**: {self.config['environment']}
- **Database**: {self.config['db_mode'].upper()} ({self.config['db_engine']})
- **PHP Version**: {self.config['php_version']}
- **WordPress Version**: {self.config['wordpress_version']}
- **SSL**: {'Enabled' if self.config['enable_ssl'] else 'Disabled'}
- **Redis Cache**: {'Enabled' if self.config['enable_redis'] else 'Disabled'}

## Quick Start
1. Install Ansible collections:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```
2. Deploy:
   ```bash
   ansible-playbook site.yml
   ```
   If using sudo: `ansible-playbook site.yml --ask-become-pass`

## Structure
- `site.yml`: Main playbook containing all tasks
- `vars/`: Configuration variables
- `templates/`: Jinja2 templates for configs
- `handlers/`: Service restart handlers
"""
        self._write_file(self.output_dir / "README.md", readme)
