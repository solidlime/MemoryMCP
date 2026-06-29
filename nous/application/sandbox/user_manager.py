"""Sandbox container home directory management.

Creates per-persona Linux users for data isolation between personas.
Each persona's code runs as their own Linux user inside the sandbox.
Home directories live on the bind-mounted volume.
"""

from __future__ import annotations

import hashlib
import logging
import re
import warnings as _warnings

logger = logging.getLogger(__name__)

SANDBOX_CONTAINER_NAME = "sandbox"

# System usernames that conflict with sandbox users
_RESERVED = frozenset({"none", "root", "nobody", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp", "proxy", "www-data", "backup", "list", "irc", "gnats"})
_FALLBACK = "sandbox_user"
_MAXLEN = 32
_PREFIX = "sbox_"


def make_username(persona: str) -> str:
    """Convert persona name to a safe sandbox directory name.

    Sanitizes characters, lowercases, adds ``sbox_`` prefix to avoid
    collisions with system users. Max 32 chars total.

    Examples::

        make_username("default")  → "sbox_default"
        make_username("None")     → "sbox_sandbox_user"
        make_username("000")      → "sbox_u_000"
    """
    name = persona.strip()
    # Replace non-alphanumeric chars (except - and _) with underscore
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    name = name.lower()
    if not name or name in _RESERVED:
        name = _FALLBACK
    if name[0].isdigit():
        name = "u_" + name
    return f"{_PREFIX}{name}"[:_MAXLEN]


def _deterministic_uid(persona: str) -> int:
    """Generate a deterministic UID from persona name (range: 10000–49999).

    This ensures the same persona always gets the same UID across container
    recreations, avoiding unnecessary ``chown -R`` rewrites on bind-mounted
    home directories.
    """
    h = hashlib.md5(persona.encode()).hexdigest()
    return int(h[:8], 16) % 40000 + 10000


def home_create_commands(persona: str) -> list[str]:
    """Generate shell commands to ensure persona home directory exists.

    Creates a Linux user for the persona (idempotent), sets up standard
    subdirectories for pip, npm, cargo, and fixes ownership.
    """
    username = make_username(persona)
    home = f"/home/{username}"
    return [
        f"id -u {username} &>/dev/null || useradd -u {_deterministic_uid(persona)} -m -d {home} -s /bin/bash {username}",
        f"mkdir -p {home}/.local {home}/.cache/pip {home}/.config/pip",
        f"mkdir -p {home}/.npm-global",
        f"chown -R {username}:{username} {home}",
        # Set PIP_USER=1 for pip install --user behavior
        f'test -f {home}/.bashrc || echo "export PIP_USER=1" > {home}/.bashrc',
        f'grep -q "PIP_USER=1" {home}/.bashrc 2>/dev/null || echo "export PIP_USER=1" >> {home}/.bashrc',
        f'grep -q ".npm-global" {home}/.bashrc 2>/dev/null || echo "export PATH={home}/.npm-global/bin:\\$PATH" >> {home}/.bashrc',
        f'grep -q ".cargo/bin" {home}/.bashrc 2>/dev/null || echo "export PATH={home}/.cargo/bin:\\$PATH" >> {home}/.bashrc',
    ]


def home_delete_commands(persona: str) -> list[str]:
    """Generate command to remove persona home directory and Linux user.

    Removes the Linux user entry (``userdel -r`` removes both /etc/passwd
    and the home directory). If the user doesn't exist in /etc/passwd but
    the home directory is still present (e.g., container rebuild with
    bind-mounted /home), falls back to ``rm -rf``.
    """
    username = make_username(persona)
    home = f"/home/{username}"
    return [
        f"id -u {username} &>/dev/null && userdel -r {username} || rm -rf {home}",
    ]


def home_exists_commands(persona: str) -> list[str]:
    """Generate command to check if Linux user exists (exit code 0 = exists).

    Uses ``id -u`` to check /etc/passwd, NOT ``test -d`` on the home
    directory. This avoids a TOCTOU race where the bind-mounted home
    directory survives container rebuild but the user entry is gone,
    causing ``docker exec --user <username>`` to fail with
    ``unable to find user``.
    """
    username = make_username(persona)
    return [f"id -u {username} &>/dev/null"]


# ---------------------------------------------------------------------------
# Deprecated — kept for backwards compatibility. Prefer home_create_commands
# directly. Linux user creation is now handled inside home_create_commands.
# ---------------------------------------------------------------------------


def user_create_commands(persona: str) -> list[str]:
    """DEPRECATED: Use home_create_commands() instead."""
    _warnings.warn("user_create_commands is deprecated, use home_create_commands", DeprecationWarning, stacklevel=2)
    return home_create_commands(persona)


def user_delete_commands(persona: str) -> list[str]:
    """DEPRECATED: Use home_delete_commands() instead."""
    _warnings.warn("user_delete_commands is deprecated, use home_delete_commands", DeprecationWarning, stacklevel=2)
    return home_delete_commands(persona)


def user_exists_commands(persona: str) -> list[str]:
    """DEPRECATED: Use home_exists_commands() instead."""
    _warnings.warn("user_exists_commands is deprecated, use home_exists_commands", DeprecationWarning, stacklevel=2)
    return home_exists_commands(persona)
