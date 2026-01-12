"""Coexistence-aware Nginx role generator."""

from pathlib import Path
from typing import Dict, Any
from .roles import RoleGenerator


class CoexistenceNginxRole(RoleGenerator):
    """Generate Nginx role that coexists with existing installation."""
    
    def generate(self) -> None:
        """Generate coexistence-friendly Nginx configuration."""
        
        # Don't install Nginx (already installed)
        # Don't remove default config (might be in use)
        # Just add WordPress site config
        
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
        self._write_file(
            self.output_dir / "roles" / "nginx" / "tasks" / "main.yml",
            tasks
        )
        
        # Same WordPress template as before
        template = """server {
    listen 80;
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
