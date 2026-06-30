"""Tests for PersonaRepository abstract interface."""

from __future__ import annotations

import pytest

from nous.domain.persona.repository import PersonaRepository
from nous.infrastructure.sqlite.connection import SQLiteConnection
from nous.infrastructure.sqlite.persona_repo import SQLitePersonaRepository


class TestPersonaRepositoryInterface:
    """Verify the abstract interface contract."""

    def test_cannot_instantiate_abstract(self):
        """PersonaRepository is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PersonaRepository()  # type: ignore[abstract]

    def test_sqlite_repo_conforms_to_interface(self, tmp_path):
        """SQLitePersonaRepository should be a concrete implementation."""
        conn = SQLiteConnection(data_dir=str(tmp_path), persona="test")
        conn.initialize_schema()
        repo = SQLitePersonaRepository(conn)
        assert isinstance(repo, PersonaRepository)
        conn.close()
