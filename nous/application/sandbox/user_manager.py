"""Sandbox container home directory management.

No longer creates Linux users. Since the sandbox container is fully isolated
at the container level, per-user Linux isolation is unnecessary overhead.
All code runs as root inside the sandbox. We only manage home directories
on the bind-mounted volume.
"""

from __future__ import annotations

import logging
import re

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


def home_create_commands(persona: str) -> list[str]:
    """Generate shell commands to ensure persona home directory exists.

    Bind-mount safe: no useradd/chown involved. Just mkdir + chmod.
    Sets up standard subdirectories for pip, npm, cargo.
    """
    username = make_username(persona)
    home = f"/home/{username}"
    return [
        f"mkdir -p {home} && chmod 777 {home}",
        f"mkdir -p {home}/.local {home}/.cache/pip {home}/.config/pip",
        f"mkdir -p {home}/.npm-global",
        # Set PIP_USER=1 for pip install --user behavior
        f'test -f {home}/.bashrc || echo "export PIP_USER=1" > {home}/.bashrc',
        f'grep -q "PIP_USER=1" {home}/.bashrc 2>/dev/null || echo "export PIP_USER=1" >> {home}/.bashrc',
        f'grep -q ".npm-global" {home}/.bashrc 2>/dev/null || echo "export PATH={home}/.npm-global/bin:\\$PATH" >> {home}/.bashrc',
        f'grep -q ".cargo/bin" {home}/.bashrc 2>/dev/null || echo "export PATH={home}/.cargo/bin:\\$PATH" >> {home}/.bashrc',
    ]


def home_delete_commands(persona: str) -> list[str]:
    """Generate command to remove persona home directory."""
    username = make_username(persona)
    home = f"/home/{username}"
    return [
        f"rm -rf {home}",
    ]


def home_exists_commands(persona: str) -> list[str]:
    """Generate command to check if home directory exists (exit code 0 = exists)."""
    username = make_username(persona)
    home = f"/home/{username}"
    return [f"test -d {home}"]


# ---------------------------------------------------------------------------
# Deprecated — kept for backwards compatibility but no longer used internally.
# All code now runs as root inside the container; Linux user creation is
# unnecessary overhead on bind-mounted volumes.
# ---------------------------------------------------------------------------

import warnings as _warnings


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
