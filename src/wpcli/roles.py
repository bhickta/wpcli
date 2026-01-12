"""Simplified role generation - all roles in one place."""

from pathlib import Path
from typing import Dict, Any


def write_file(path: Path, content: str) -> None:
    """Write content to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def generate_all_roles(output_dir: Path, config: Dict[str, Any]) -> None:
    """Generate all Ansible roles."""
    # Check if coexistence mode
    use_coexistence = config.get("nginx_coexistence", False)
    
    generate_prerequisites(output_dir)
    generate_database(output_dir, config)
    generate_php(output_dir)
    
    if use_coexistence:
        generate_nginx_coexistence(output_dir)
    else:
        generate_nginx(output_dir)
    
    generate_wordpress(output_dir)
    generate_ssl(output_dir)
    generate_redis(output_dir)
    generate_monitoring(output_dir)
    generate_backup(output_dir)
    generate_security(output_dir)


def generate_prerequisites(output_dir: Path) -> None:
    """Generate prerequisites role."""
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
    write_file(output_dir / "roles" / "prerequisites" / "tasks" / "main.yml", tasks)


def generate_database(output_dir: Path, config: Dict[str, Any]) -> None:
    """Generate database role."""
    engine = config.get("db_engine", "mysql")
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
    name: "{{{{ item.db_name }}}}"
    state: present
    encoding: utf8mb4
    collation: utf8mb4_unicode_ci
    login_user: root
    login_password: "{{{{ db_password }}}}"
  loop: "{{{{ wordpress_sites }}}}"

- name: Create WordPress database user
  community.mysql.mysql_user:
    name: "{{{{ item.db_user }}}}"
    password: "{{{{ db_password }}}}"
    priv: "{{{{ item.db_name }}}}.*:ALL"
    state: present
    login_user: root
    login_password: "{{{{ db_password }}}}"
  loop: "{{{{ wordpress_sites }}}}"

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
    write_file(output_dir / "roles" / "database" / "tasks" / "main.yml", tasks)
    
    handler = f"""---
- name: restart {service}
  service:
    name: {service}
    state: restarted
"""
    write_file(output_dir / "roles" / "database" / "handlers" / "main.yml", handler)


def generate_php(output_dir: Path) -> None:
    """Generate PHP role."""
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
    write_file(output_dir / "roles" / "php" / "tasks" / "main.yml", tasks)
    
    handler = """---
- name: restart php-fpm
  service:
    name: "php{{ php_version }}-fpm"
    state: restarted
"""
    write_file(output_dir / "roles" / "php" / "handlers" / "main.yml", handler)


def generate_nginx(output_dir: Path) -> None:
    """Generate Nginx role (standard)."""
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
    write_file(output_dir / "roles" / "nginx" / "tasks" / "main.yml", tasks)
    _write_nginx_template_and_handlers(output_dir)


def generate_nginx_coexistence(output_dir: Path) -> None:
    """Generate Nginx role (coexistence mode)."""
    tasks = """---
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
    src: wordpress.conf.j2
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
    write_file(output_dir / "roles" / "nginx" / "tasks" / "main.yml", tasks)
    _write_nginx_template_and_handlers(output_dir)


def _write_nginx_template_and_handlers(output_dir: Path) -> None:
    """Write Nginx template and handlers (shared)."""
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
    write_file(output_dir / "roles" / "nginx" / "templates" / "wordpress.conf.j2", template)
    
    handler = """---
- name: restart nginx
  service:
    name: nginx
    state: restarted

- name: reload nginx
  service:
    name: nginx
    state: reloaded
"""
    write_file(output_dir / "roles" / "nginx" / "handlers" / "main.yml", handler)


def generate_wordpress(output_dir: Path) -> None:
    """Generate WordPress role."""
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
    write_file(output_dir / "roles" / "wordpress" / "tasks" / "main.yml", tasks)
    
    # Fixed wp-config template - use item.enable_ssl instead of enable_ssl
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
    write_file(output_dir / "roles" / "wordpress" / "templates" / "wp-config.php.j2", wp_config)


def generate_ssl(output_dir: Path) -> None:
    """Generate SSL role."""
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
    write_file(output_dir / "roles" / "ssl" / "tasks" / "main.yml", tasks)


def generate_redis(output_dir: Path) -> None:
    """Generate Redis role."""
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
  when: item.enable_cache

- name: Enable Redis object cache
  command: >
    wp redis enable
    --path="{{ web_root }}/{{ item.domain }}"
    --allow-root
  loop: "{{ wordpress_sites }}"
  when: item.enable_cache
  ignore_errors: yes
"""
    write_file(output_dir / "roles" / "redis" / "tasks" / "main.yml", tasks)
    
    handler = """---
- name: restart redis
  service:
    name: redis-server
    state: restarted
"""
    write_file(output_dir / "roles" / "redis" / "handlers" / "main.yml", handler)


def generate_monitoring(output_dir: Path) -> None:
    """Generate monitoring role."""
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
    write_file(output_dir / "roles" / "monitoring" / "tasks" / "main.yml", tasks)


def generate_backup(output_dir: Path) -> None:
    """Generate backup role."""
    tasks = """---
- name: Create backup directory
  file:
    path: /var/backups/wordpress
    state: directory
    mode: '0700'

- name: Create database backup script
  template:
    src: backup-db.sh.j2
    dest: /usr/local/bin/backup-wordpress-db.sh
    mode: '0755'

- name: Schedule database backups
  cron:
    name: "WordPress database backup"
    minute: "0"
    hour: "2"
    job: "/usr/local/bin/backup-wordpress-db.sh"
"""
    write_file(output_dir / "roles" / "backup" / "tasks" / "main.yml", tasks)
    
    script = """#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
{% for site in wordpress_sites %}
mysqldump -h {{ db_host }} -u {{ site.db_user }} -p'{{ db_password }}' {{ site.db_name }} | gzip > /var/backups/wordpress/{{ site.domain }}_${DATE}.sql.gz
{% endfor %}
find /var/backups/wordpress -name "*.sql.gz" -mtime +7 -delete
"""
    write_file(output_dir / "roles" / "backup" / "templates" / "backup-db.sh.j2", script)


def generate_security(output_dir: Path) -> None:
    """Generate security role."""
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
    write_file(output_dir / "roles" / "security" / "tasks" / "main.yml", tasks)
    
    handler = """---
- name: restart fail2ban
  service:
    name: fail2ban
    state: restarted
"""
    write_file(output_dir / "roles" / "security" / "handlers" / "main.yml", handler)
