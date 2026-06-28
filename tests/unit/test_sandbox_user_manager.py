"""Tests for sandbox user manager."""

from unittest.mock import MagicMock, patch

import pytest

from nous.application.sandbox.service import (
    _sessions,
    get_sandbox_session,
)
from nous.application.sandbox.user_manager import (
    SANDBOX_CONTAINER_NAME,
    make_username,
    user_create_commands,
    user_delete_commands,
    user_exists_commands,
)


class TestMakeUsername:
    def test_standard_name(self):
        assert make_username("alice") == "sbox_alice"

    def test_hyphen_preserved(self):
        assert make_username("my-persona") == "sbox_my-persona"

    def test_underscore_preserved(self):
        assert make_username("test_user") == "sbox_test_user"

    def test_uppercase_lowered(self):
        assert make_username("Alice") == "sbox_alice"

    def test_special_chars_replaced(self):
        assert make_username("hello@world!") == "sbox_hello_world_"

    def test_none_string_fallback(self):
        """'None' is reserved → fallback."""
        result = make_username("None")
        assert result == "sbox_sandbox_user"

    def test_empty_string_fallback(self):
        result = make_username("")
        assert result == "sbox_sandbox_user"

    def test_whitespace_fallback(self):
        result = make_username("  \t  ")
        assert result == "sbox_sandbox_user"

    def test_root_reserved(self):
        result = make_username("root")
        assert result == "sbox_sandbox_user"

    def test_nobody_reserved(self):
        result = make_username("nobody")
        assert result == "sbox_sandbox_user"

    def test_starts_with_digit(self):
        result = make_username("000agent")
        assert result == "sbox_u_000agent"

    def test_truncated_to_maxlen(self):
        long_name = "a" * 100
        result = make_username(long_name)
        assert len(result) <= 32
        assert result.startswith("sbox_")
        assert result == "sbox_" + "a" * 27

    def test_prefix_enforced(self):
        assert make_username("bob").startswith("sbox_")


class TestUserCreateCommands:
    def test_generates_idempotent_commands(self):
        cmds = user_create_commands("test_user")
        assert len(cmds) > 0
        joined = " ".join(cmds)
        assert "useradd" in joined
        # First command checks id before useradd
        assert "id -u" in cmds[0]

    def test_useradd_with_group_flags(self):
        cmds = user_create_commands("test_user")
        text = " ".join(cmds)
        assert "-U" in text  # Creates group with same name
        assert "groupadd" in text  # Fallback if group not created

    def test_generates_pip_user_setup(self):
        cmds = user_create_commands("test_user")
        text = " ".join(cmds)
        assert "PIP_USER=1" in text

    def test_generates_npm_global_setup(self):
        cmds = user_create_commands("test_user")
        text = " ".join(cmds)
        assert ".npm-global" in text

    def test_includes_home_directory(self):
        cmds = user_create_commands("bob")
        text = " ".join(cmds)
        assert "/home/sbox_bob" in text

    def test_chown_applied(self):
        cmds = user_create_commands("testuser")
        text = " ".join(cmds)
        assert "chown" in text
        assert "sbox_testuser:sbox_testuser" in text


class TestUserDeleteCommands:
    def test_generates_delete_command(self):
        cmds = user_delete_commands("test_user")
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
        cmds = user_exists_commands("test_user")
        text = " ".join(cmds)
        assert "id -u" in text
        assert "sbox_test_user" in text


class TestConstants:
    def test_container_name(self):
        assert SANDBOX_CONTAINER_NAME == "sandbox"


# ============================================================================
# Service-level integration tests (with Docker mocked)
# ============================================================================


@pytest.fixture
def mock_docker():
    """Fixture that mocks docker.from_env() and returns a mock container."""
    with patch("nous.application.sandbox.service.docker.from_env") as mock_from_env:
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        # exec_run returns (exit_code, output)
        # Default: user exists (exit_code 0)
        mock_container.exec_run.return_value = (0, (b"uid=1001", b""))

        yield mock_client, mock_container, mock_from_env


class TestEnsureSandboxUser:
    """Tests for ensure_sandbox_user() — standalone user creation."""

    @pytest.mark.asyncio
    async def test_user_already_exists(self, mock_docker):
        """Should not recreate user if already exists."""
        mock_client, mock_container, _ = mock_docker
        mock_container.exec_run.return_value = (0, (b"uid=1001", b""))

        from nous.application.sandbox.service import ensure_sandbox_user

        result = await ensure_sandbox_user("test_persona")

        assert result == "sbox_test_persona"
        assert mock_container.exec_run.call_count == 1
        call_args = mock_container.exec_run.call_args[0]
        assert "id -u" in " ".join(call_args[0] if isinstance(call_args[0], list) else [str(call_args[0])])

    @pytest.mark.asyncio
    async def test_user_not_exists_creates(self, mock_docker):
        """Should create user when not exists."""
        mock_client, mock_container, _ = mock_docker
        # First call: user does not exist (exit_code 1)
        # Second call: create succeeds (exit_code 0)
        mock_container.exec_run.side_effect = [
            (1, (b"", b"id: user not found")),
            (0, (b"", b"")),
        ]

        from nous.application.sandbox.service import ensure_sandbox_user

        result = await ensure_sandbox_user("new_user")

        assert result == "sbox_new_user"
        assert mock_container.exec_run.call_count == 2
        # Second call should contain useradd
        second_call = mock_container.exec_run.call_args_list[1]
        cmd = " ".join(second_call[0][0] if isinstance(second_call[0][0], list) else [str(second_call[0][0])])
        assert "useradd" in cmd

    @pytest.mark.asyncio
    async def test_creation_failure_logged(self, mock_docker):
        """Should log warning but return username on creation failure."""
        mock_client, mock_container, _ = mock_docker
        mock_container.exec_run.side_effect = [
            (1, (b"", b"")),
            (1, (b"", b"useradd: cannot lock /etc/passwd")),
        ]

        from nous.application.sandbox.service import ensure_sandbox_user

        # Should not raise — just log warning
        result = await ensure_sandbox_user("fail_user")
        assert result == "sbox_fail_user"

    @pytest.mark.asyncio
    async def test_container_not_found(self, mock_docker):
        """Should raise RuntimeError if sandbox container missing."""
        mock_client, _, mock_from_env = mock_docker
        mock_client.containers.get.side_effect = __import__("docker").errors.NotFound("sandbox", "not found")

        from nous.application.sandbox.service import ensure_sandbox_user

        with pytest.raises(RuntimeError, match="Sandbox container.*not found"):
            await ensure_sandbox_user("test_user")


class TestDeleteSandboxUser:
    """Tests for delete_sandbox_user() — standalone user deletion."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_docker):
        """Should return True when user deleted successfully."""
        mock_client, mock_container, _ = mock_docker
        mock_container.exec_run.return_value = (0, (b"", b""))

        from nous.application.sandbox.service import delete_sandbox_user

        result = await delete_sandbox_user("deleteme")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_failure(self, mock_docker):
        """Should return False when deletion fails."""
        mock_client, mock_container, _ = mock_docker
        mock_container.exec_run.return_value = (1, (b"", b"userdel: user is logged in"))

        from nous.application.sandbox.service import delete_sandbox_user

        result = await delete_sandbox_user("busy_user")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, mock_docker):
        """Should return True for nonexistent user (userdel exits 0 via || true)."""
        mock_client, mock_container, _ = mock_docker
        # user_delete_commands uses || true so exit_code 0
        mock_container.exec_run.return_value = (0, (b"", b""))

        from nous.application.sandbox.service import delete_sandbox_user

        result = await delete_sandbox_user("nonexistent")
        assert result is True


class TestGetSandboxSession:
    """Tests for get_sandbox_session() — session creation with user ensure."""

    @pytest.mark.asyncio
    async def test_new_session_ensures_user(self, mock_docker):
        """First call should call ensure_sandbox_user (via docker exec)."""
        mock_client, mock_container, _ = mock_docker
        mock_container.exec_run.return_value = (0, (b"uid=1001", b""))

        _sessions.clear()  # Ensure clean state

        session = await get_sandbox_session("new_persona")

        assert session is not None
        assert session.persona == "new_persona"
        # Should have called docker exec at least once (via ensure_sandbox_user)
        assert mock_container.exec_run.called

    @pytest.mark.asyncio
    async def test_existing_session_returns_cached(self, mock_docker):
        """Second call should return cached session without docker calls."""
        mock_client, mock_container, _ = mock_docker
        mock_container.exec_run.return_value = (0, (b"uid=1001", b""))

        _sessions.clear()

        # First call — creates session
        session1 = await get_sandbox_session("cached_user")

        # Reset mock to detect new calls
        mock_container.exec_run.reset_mock()

        # Second call — should use cache
        session2 = await get_sandbox_session("cached_user")

        assert session1 is session2  # Same object (cached)
        assert not mock_container.exec_run.called  # No docker calls

    @pytest.mark.asyncio
    async def test_multiple_personas_isolated(self, mock_docker):
        """Different personas should get different sessions."""
        mock_client, mock_container, _ = mock_docker
        mock_container.exec_run.return_value = (0, (b"uid=1001", b""))

        _sessions.clear()

        s1 = await get_sandbox_session("alice")
        s2 = await get_sandbox_session("bob")

        assert s1 is not s2
        assert s1.persona == "alice"
        assert s2.persona == "bob"
