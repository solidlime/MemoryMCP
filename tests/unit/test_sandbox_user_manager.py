"""Tests for sandbox user manager."""

import pytest
from nous.application.sandbox.user_manager import (
    make_username,
    user_create_commands,
    user_delete_commands,
    user_exists_commands,
    SANDBOX_CONTAINER_NAME,
)


class TestMakeUsername:
    def test_default_persona(self):
        assert make_username("default") == "default"

    def test_custom_persona(self):
        assert make_username("my-persona") == "my-persona"

    def test_no_prefix(self):
        # Username = persona name, no prefix like "sandbox-"
        assert make_username("alice") == "alice"


class TestUserCreateCommands:
    def test_generates_idempotent_commands(self):
        cmds = user_create_commands("default")
        assert len(cmds) > 0
        joined = " ".join(cmds)
        assert "useradd" in joined
        # First command checks id before useradd
        assert "id -u" in cmds[0]

    def test_generates_pip_user_setup(self):
        cmds = user_create_commands("default")
        text = " ".join(cmds)
        assert "PIP_USER=1" in text

    def test_generates_npm_global_setup(self):
        cmds = user_create_commands("default")
        text = " ".join(cmds)
        assert ".npm-global" in text

    def test_includes_home_directory(self):
        cmds = user_create_commands("bob")
        text = " ".join(cmds)
        assert "/home/bob" in text

    def test_chown_applied(self):
        cmds = user_create_commands("testuser")
        text = " ".join(cmds)
        assert "chown" in text
        assert "testuser:testuser" in text


class TestUserDeleteCommands:
    def test_generates_delete_command(self):
        cmds = user_delete_commands("default")
        text = " ".join(cmds)
        assert "userdel" in text

    def test_safe_for_missing_user(self):
        cmds = user_delete_commands("nonexistent")
        text = " ".join(cmds)
        assert "|| true" in text

    def test_deletes_home_directory(self):
        cmds = user_delete_commands("alice")
        text = " ".join(cmds)
        assert "userdel -r" in text  # -r flag removes home dir


class TestUserExistsCommands:
    def test_generates_id_check(self):
        cmds = user_exists_commands("default")
        text = " ".join(cmds)
        assert "id -u" in text
        assert "default" in text


class TestConstants:
    def test_container_name(self):
        assert SANDBOX_CONTAINER_NAME == "sandbox"
