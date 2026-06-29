"""Tests for sandbox user manager."""

from unittest.mock import MagicMock, patch

import pytest

from nous.application.sandbox.service import (
    SandboxSession,
    _sessions,
    get_sandbox_session,
)
from nous.application.sandbox.user_manager import (
    SANDBOX_CONTAINER_NAME,
    home_create_commands,
    home_delete_commands,
    home_exists_commands,
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

    def test_useradd_with_flags(self):
        cmds = user_create_commands("test_user")
        text = " ".join(cmds)
        assert "-u" in text  # Deterministic UID
        assert "-m -d" in text  # Create home directory
        assert "-s /bin/bash" in text  # Set shell

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
        assert "userdel -r" in text

    def test_safe_for_missing_user(self):
        cmds = user_delete_commands("nonexistent")
        text = " ".join(cmds)
        assert "rm -rf" in text  # fallback when user doesn't exist
        assert "userdel" in text
        assert "||" in text

    def test_deletes_home_directory(self):
        cmds = user_delete_commands("alice")
        text = " ".join(cmds)
        assert "userdel -r" in text
        assert "/home/sbox_alice" in text


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


# ============================================================================
# home_create_commands detailed structure tests
# ============================================================================


class TestUserCreationDetails:
    """Tests for home_create_commands() — detailed command structure."""

    def test_useradd_is_first_command(self):
        """useradd should be in the first command (after id -u existence check)."""
        cmds = home_create_commands("test_user")
        assert cmds[0].startswith("id -u")
        assert "useradd" in cmds[0]

    def test_creates_home_with_correct_path(self):
        """useradd -d should use correct home path for the username."""
        cmds = home_create_commands("test_user")
        assert "-d /home/sbox_test_user" in cmds[0]

    def test_chown_runs_after_mkdir(self):
        """chown should appear after all mkdir commands."""
        cmds = home_create_commands("test_user")
        mkdir_indices = [i for i, c in enumerate(cmds) if c.startswith("mkdir")]
        chown_indices = [i for i, c in enumerate(cmds) if c.startswith("chown")]
        assert mkdir_indices, "Expected at least one mkdir command"
        assert chown_indices, "Expected at least one chown command"
        assert all(ci > mi for ci in chown_indices for mi in mkdir_indices)

    def test_bashrc_contains_pip_user(self):
        """.bashrc setup should include PIP_USER=1."""
        cmds = home_create_commands("test_user")
        bashrc_cmds = [c for c in cmds if ".bashrc" in c]
        assert len(bashrc_cmds) >= 1
        pip_lines = [c for c in bashrc_cmds if "PIP_USER=1" in c]
        assert len(pip_lines) >= 1

    def test_all_commands_present(self):
        """useradd, mkdir, chown, PIP_USER should all be present in commands."""
        cmds = home_create_commands("test_user")
        text = " ".join(cmds)
        assert "useradd" in text
        assert "mkdir -p" in text
        assert "chown -R" in text
        assert "PIP_USER=1" in text


# ============================================================================
# home_delete_commands detailed structure tests
# ============================================================================


class TestUserDeletionDetails:
    """Tests for home_delete_commands() — detailed command structure."""

    def test_delete_removes_user_and_home(self):
        """Delete command should userdel -r then fallback to rm -rf."""
        cmds = home_delete_commands("test_user")
        assert "userdel -r" in cmds[0]
        assert "/home/sbox_test_user" in cmds[0]
        assert "|| rm -rf" in cmds[0]

    def test_delete_targets_correct_user(self):
        """Delete command should target the correct username's home."""
        cmds = home_delete_commands("alice")
        assert "sbox_alice" in cmds[0]


# ============================================================================
# home_exists_commands detailed structure tests
# ============================================================================


class TestUserExistenceDetails:
    """Tests for home_exists_commands() — detailed command structure."""

    def test_exists_checks_user_in_passwd(self):
        """Exists command should use id -u (not test -d) to avoid TOCTOU."""
        cmds = home_exists_commands("test_user")
        assert "id -u" in cmds[0]
        assert "sbox_test_user" in cmds[0]
        assert "/home" not in cmds[0]


# ============================================================================
# Code execution isolation tests (SandboxSession._exec_user with mock Docker)
# ============================================================================


class TestCodeExecutionIsolation:
    """Tests for SandboxSession._exec_user() — persona user isolation."""

    @pytest.mark.asyncio
    async def test_exec_user_runs_as_persona_user(self, mock_docker):
        """_exec_user should call exec_run with user=self.username."""
        mock_client, mock_container, _ = mock_docker
        _sessions.clear()

        session = SandboxSession("test_persona")
        session._container = mock_container  # Pre-set to skip _ensure_container

        await session._exec_user("echo hello")

        mock_container.exec_run.assert_called_once()
        _, kwargs = mock_container.exec_run.call_args
        assert kwargs.get("user") == "sbox_test_persona"

    @pytest.mark.asyncio
    async def test_exec_user_sets_correct_workdir(self, mock_docker):
        """_exec_user should default workdir to /home/{username}."""
        mock_client, mock_container, _ = mock_docker
        _sessions.clear()

        session = SandboxSession("test_persona")
        session._container = mock_container

        await session._exec_user("pwd")

        args, kwargs = mock_container.exec_run.call_args
        wrapped = args[0]
        cmd_str = " ".join(wrapped)
        # The wrapped command includes "cd /home/{username} && pwd"
        assert "/home/sbox_test_persona" in cmd_str

    @pytest.mark.asyncio
    async def test_exec_user_sets_environment(self, mock_docker):
        """_exec_user should set HOME, USER, PATH, PIP_USER in environment."""
        mock_client, mock_container, _ = mock_docker
        _sessions.clear()

        session = SandboxSession("test_persona")
        session._container = mock_container

        await session._exec_user("env")

        _, kwargs = mock_container.exec_run.call_args
        env = kwargs.get("environment", {})
        assert env.get("HOME") == "/home/sbox_test_persona"
        assert env.get("USER") == "sbox_test_persona"
        assert "PATH" in env
        assert env.get("PIP_USER") == "1"

    @pytest.mark.asyncio
    async def test_different_personas_isolation(self, mock_docker):
        """Different personas should get different usernames and workdirs."""
        mock_client, mock_container, _ = mock_docker
        _sessions.clear()

        s1 = SandboxSession("alice")
        s2 = SandboxSession("bob")
        s1._container = mock_container
        s2._container = mock_container

        # Different usernames
        assert s1.username == "sbox_alice"
        assert s2.username == "sbox_bob"
        assert s1.username != s2.username

        # Different home directories via _build_env
        env1 = s1._build_env()
        env2 = s2._build_env()
        assert env1["HOME"] != env2["HOME"]
        assert env1["USER"] != env2["USER"]

        # Different exec_run calls with different workdirs
        await s1._exec_user("whoami")
        await s2._exec_user("whoami")

        args1, _ = mock_container.exec_run.call_args_list[0]
        args2, _ = mock_container.exec_run.call_args_list[1]
        assert "/home/sbox_alice" in " ".join(args1[0])
        assert "/home/sbox_bob" in " ".join(args2[0])

    @pytest.mark.asyncio
    async def test_exec_user_error_handling(self, mock_docker):
        """exec_run exception should return empty string and error message."""
        mock_client, mock_container, _ = mock_docker
        _sessions.clear()

        mock_container.exec_run.side_effect = RuntimeError("connection lost")

        session = SandboxSession("test_persona")
        session._container = mock_container

        stdout, stderr, exit_code = await session._exec_user("echo hello")

        assert stdout == ""
        assert "connection lost" in stderr
        assert exit_code == 1
