"""Ansible role generators - each role in its own focused module."""

from pathlib import Path
from typing import Dict, Any


class RoleGenerator:
    """Base class for role generators."""
    
    def __init__(self, output_dir: Path, config: Dict[str, Any]):
        self.output_dir = output_dir
        self.config = config
    
    def _write_file(self, path: Path, content: str) -> None:
        """Write content to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    
    def generate(self) -> None:
        """Generate the role. Must be implemented by subclasses."""
        raise NotImplementedError


class PrerequisitesRole(RoleGenerator):
    """Generate prerequisites role."""
    
    def generate(self) -> None:
        tasks = """---
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
        self._write_file(
            self.output_dir / "roles" / "prerequisites" / "tasks" / "main.yml",
            tasks
        )


class DatabaseRole(RoleGenerator):
    """Generate database role (MySQL/MariaDB)."""
    
    def generate(self) -> None:
        engine = self.config.get("db_engine", "mysql")
        package = "mariadb-server" if engine == "mariadb" else "mysql-server"
        service = "mariadb" if engine == "mariadb" else "mysql"
        
        tasks = f"""---
- name: Install {engine.upper()}
  apt:
    name:
      - {package}
      - {package.replace('-server', '-client')}
    state: present

- name: Start and enable {engine.upper()}
  service:
    name: {service}
    state: started
    enabled: yes

- name: Set root password
  community.mysql.mysql_user:
    name: root
    password: "{{{{ db_password }}}}"
    login_unix_socket: /var/run/mysqld/mysqld.sock
    state: present
  ignore_errors: yes

- name: Remove anonymous users
  community.mysql.mysql_user:
    name: ''
    host_all: yes
    state: absent
    login_user: root
    login_password: "{{{{ db_password }}}}"

- name: Remove test database
  community.mysql.mysql_db:
    name: test
    state: absent
    login_user: root
    login_password: "{{{{ db_password }}}}"

- name: Create WordPress database
  community.mysql.mysql_db:
    name: "{{{{ db_name }}}}"
    state: present
    encoding: utf8mb4
    collation: utf8mb4_unicode_ci
    login_user: root
    login_password: "{{{{ db_password }}}}"

- name: Create WordPress database user
  community.mysql.mysql_user:
    name: "{{{{ db_user }}}}"
    password: "{{{{ db_password }}}}"
    priv: "{{{{ db_name }}}}.*:ALL"
    state: present
    login_user: root
    login_password: "{{{{ db_password }}}}"

- name: Configure {engine.upper()} performance
  lineinfile:
    path: /etc/mysql/mysql.conf.d/mysqld.cnf
    line: "{{{{ item }}}}"
    insertafter: '^\\[mysqld\\]'
  loop:
    - "innodb_buffer_pool_size = 256M"
    - "max_connections = 200"
  notify: restart {service}
"""
        self._write_file(
            self.output_dir / "roles" / "database" / "tasks" / "main.yml",
            tasks
        )
        
        handler = f"""---
- name: restart {service}
  service:
    name: {service}
    state: restarted
"""
        self._write_file(
            self.output_dir / "roles" / "database" / "handlers" / "main.yml",
            handler
        )


class NginxRole(RoleGenerator):
    """Generate Nginx role."""
    
    def generate(self) -> None:
        tasks = """---
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
    src: wordpress.conf.j2
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
        self._write_file(
            self.output_dir / "roles" / "nginx" / "tasks" / "main.yml",
            tasks
        )
        
        template = """server {
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
        self._write_file(
            self.output_dir / "roles" / "nginx" / "templates" / "wordpress.conf.j2",
            template
        )


class PHPRole(RoleGenerator):
    """Generate PHP role."""
    
    def generate(self) -> None:
        tasks = """---
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
        self._write_file(
            self.output_dir / "roles" / "php" / "tasks" / "main.yml",
            tasks
        )


class WordPressRole(RoleGenerator):
    """Generate WordPress role."""
    
    def generate(self) -> None:
        tasks = """---
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
    src: wp-config.php.j2
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
        self._write_file(
            self.output_dir / "roles" / "wordpress" / "tasks" / "main.yml",
            tasks
        )
        
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

{% if enable_redis %}
define( 'WP_REDIS_HOST', '{{ redis_host }}' );
define( 'WP_REDIS_PORT', {{ redis_port }} );
define( 'WP_CACHE', true );
{% endif %}

define( 'WP_DEBUG', {{ 'true' if deployment_env == 'development' else 'false' }} );
define( 'DISALLOW_FILE_EDIT', true );
define( 'FORCE_SSL_ADMIN', {{ 'true' if enable_ssl else 'false' }} );

if ( ! defined( 'ABSPATH' ) ) {
\tdefine( 'ABSPATH', __DIR__ . '/' );
}
require_once ABSPATH . 'wp-settings.php';
"""
        self._write_file(
            self.output_dir / "roles" / "wordpress" / "templates" / "wp-config.php.j2",
            wp_config
        )


class SSLRole(RoleGenerator):
    """Generate SSL role."""
    
    def generate(self) -> None:
        tasks = """---
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
"""
        self._write_file(
            self.output_dir / "roles" / "ssl" / "tasks" / "main.yml",
            tasks
        )


class RedisRole(RoleGenerator):
    """Generate Redis role."""
    
    def generate(self) -> None:
        tasks = """---
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
  when: enable_redis

- name: Enable Redis object cache
  command: >
    wp redis enable
    --path="{{ web_root }}/{{ item.domain }}"
    --allow-root
  loop: "{{ wordpress_sites }}"
  when: enable_redis
  ignore_errors: yes
"""
        self._write_file(
            self.output_dir / "roles" / "redis" / "tasks" / "main.yml",
            tasks
        )
        
        handler = """---
- name: restart redis
  service:
    name: redis-server
    state: restarted
"""
        self._write_file(
            self.output_dir / "roles" / "redis" / "handlers" / "main.yml",
            handler
        )


class MonitoringRole(RoleGenerator):
    """Generate monitoring role."""
    
    def generate(self) -> None:
        tasks = """---
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
"""
        self._write_file(
            self.output_dir / "roles" / "monitoring" / "tasks" / "main.yml",
            tasks
        )


class BackupRole(RoleGenerator):
    """Generate backup role."""
    
    def generate(self) -> None:
        tasks = """---
- name: Create backup directory
  file:
    path: /var/backups/wordpress
    state: directory
    mode: '0700'

- name: Create database backup script
  copy:
    dest: /usr/local/bin/backup-wordpress-db.sh
    mode: '0755'
    content: |
      #!/bin/bash
      DATE=$(date +%Y%m%d_%H%M%S)
      mysqldump -u {{ db_user }} -p'{{ db_password }}' {{ db_name }} | gzip > /var/backups/wordpress/db_${DATE}.sql.gz
      find /var/backups/wordpress -name "db_*.sql.gz" -mtime +7 -delete

- name: Schedule database backups
  cron:
    name: "WordPress database backup"
    minute: "0"
    hour: "2"
    job: "/usr/local/bin/backup-wordpress-db.sh"
"""
        self._write_file(
            self.output_dir / "roles" / "backup" / "tasks" / "main.yml",
            tasks
        )


class SecurityRole(RoleGenerator):
    """Generate security role."""
    
    def generate(self) -> None:
        tasks = """---
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
"""
        self._write_file(
            self.output_dir / "roles" / "security" / "tasks" / "main.yml",
            tasks
        )
        
        handler = """---
- name: restart fail2ban
  service:
    name: fail2ban
    state: restarted
"""
        self._write_file(
            self.output_dir / "roles" / "security" / "handlers" / "main.yml",
            handler
        )


# Role registry for easy access
ROLE_GENERATORS = {
    "prerequisites": PrerequisitesRole,
    "database": DatabaseRole,
    "nginx": NginxRole,
    "php": PHPRole,
    "wordpress": WordPressRole,
    "ssl": SSLRole,
    "redis": RedisRole,
    "monitoring": MonitoringRole,
    "backup": BackupRole,
    "security": SecurityRole,
}
