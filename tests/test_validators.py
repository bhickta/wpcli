"""Tests for validators module."""

import pytest
from wpcli.validators import (
    validate_ip,
    validate_domain,
    validate_email,
    validate_db_name,
    validate_db_user,
    validate_php_version,
    validate_wordpress_version,
)


class TestIPValidation:
    def test_valid_ipv4(self):
        is_valid, result = validate_ip("192.168.1.1")
        assert is_valid is True
        assert result == "192.168.1.1"

    def test_valid_ipv6(self):
        is_valid, result = validate_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        assert is_valid is True

    def test_invalid_ip(self):
        is_valid, result = validate_ip("999.999.999.999")
        assert is_valid is False


class TestDomainValidation:
    def test_valid_domain(self):
        is_valid, result = validate_domain("example.com")
        assert is_valid is True
        assert result == "example.com"

    def test_valid_subdomain(self):
        is_valid, result = validate_domain("blog.example.com")
        assert is_valid is True

    def test_invalid_domain(self):
        is_valid, result = validate_domain("invalid domain")
        assert is_valid is False


class TestEmailValidation:
    def test_valid_email(self):
        is_valid, result = validate_email("admin@example.com")
        assert is_valid is True
        assert result == "admin@example.com"

    def test_invalid_email(self):
        is_valid, result = validate_email("not-an-email")
        assert is_valid is False


class TestDatabaseValidation:
    def test_valid_db_name(self):
        is_valid, result = validate_db_name("wordpress_db")
        assert is_valid is True
        assert result == "wordpress_db"

    def test_invalid_db_name_special_chars(self):
        is_valid, result = validate_db_name("wordpress-db")
        assert is_valid is False

    def test_invalid_db_name_too_long(self):
        is_valid, result = validate_db_name("a" * 65)
        assert is_valid is False

    def test_valid_db_user(self):
        is_valid, result = validate_db_user("wpuser")
        assert is_valid is True


class TestPHPVersion:
    def test_valid_php_version(self):
        is_valid, result = validate_php_version("8.2")
        assert is_valid is True
        assert result == "8.2"

    def test_invalid_php_version(self):
        is_valid, result = validate_php_version("7.4")
        assert is_valid is False


class TestWordPressVersion:
    def test_valid_wordpress_version(self):
        is_valid, result = validate_wordpress_version("6.4.2")
        assert is_valid is True
        assert result == "6.4.2"

    def test_valid_wordpress_version_short(self):
        is_valid, result = validate_wordpress_version("6.4")
        assert is_valid is True

    def test_invalid_wordpress_version(self):
        is_valid, result = validate_wordpress_version("invalid")
        assert is_valid is False
