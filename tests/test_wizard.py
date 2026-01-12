"""Tests for wizard module."""

import pytest
from wpcli.wizard import generate_password, generate_salt


class TestPasswordGeneration:
    def test_password_length(self):
        password = generate_password(20)
        assert len(password) == 20

    def test_password_custom_length(self):
        password = generate_password(32)
        assert len(password) == 32

    def test_password_uniqueness(self):
        passwords = [generate_password() for _ in range(10)]
        assert len(set(passwords)) == 10  # All unique


class TestSaltGeneration:
    def test_salt_length(self):
        salt = generate_salt()
        assert len(salt) == 64

    def test_salt_uniqueness(self):
        salts = [generate_salt() for _ in range(10)]
        assert len(set(salts)) == 10  # All unique
