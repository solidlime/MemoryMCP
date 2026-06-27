"""Per-persona Linux user management inside sandbox container."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SANDBOX_CONTAINER_NAME = "sandbox"


def make_username(persona: str) -> str:
    """Convert persona name to sandbox username.
    
    Persona name IS the Linux username. Sanitize if needed.
    Maps: persona="default" → username="default"
    """
    return persona


def user_create_commands(persona: str) -> list[str]:
    """Generate shell commands to create a persona user inside sandbox.
    
    Creates user if not exists, ensures home directory, sets up pip user dir.
    Idempotent — safe to run multiple times.
    Username = persona name (no prefix).
    """
    username = persona
    home = f"/home/{username}"
    return [
        # Create user if not exists (idempotent via id check)
        f'id -u {username} &>/dev/null || useradd -m -d {home} -s /bin/bash {username}',
        # Set pip to install packages to user home (persistent via volume)
        f'mkdir -p {home}/.local {home}/.cache/pip {home}/.config/pip',
        f'chown -R {username}:{username} {home}',
        # Set PIP_USER=1 for the user so pip install goes to ~/.local
        f'echo "export PIP_USER=1" >> {home}/.bashrc',
        # Set npm prefix for user-local installs
        f'mkdir -p {home}/.npm-global',
        f'echo "export PATH={home}/.npm-global/bin:\\$PATH" >> {home}/.bashrc',
        f'chown -R {username}:{username} {home}/.npm-global',
        # Rust cargo bin for user
        f'echo "export PATH={home}/.cargo/bin:\\$PATH" >> {home}/.bashrc',
    ]


def user_delete_commands(persona: str) -> list[str]:
    """Generate commands to delete a persona user (cleanup on persona deletion)."""
    username = make_username(persona)
    return [
        f'id -u {username} &>/dev/null && userdel -r {username} || true',
    ]


def user_exists_commands(persona: str) -> list[str]:
    """Generate command to check if user exists (exit code 0 = exists)."""
    username = make_username(persona)
    return [f'id -u {username}']
