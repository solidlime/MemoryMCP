from __future__ import annotations

import sqlite3

from memory_mcp.domain.skill import Skill, SkillRepository


def _make_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("""
        CREATE TABLE skills (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            content     TEXT NOT NULL DEFAULT '',
            created_at  TEXT,
            updated_at  TEXT
        )
    """)
    db.commit()
    return db


class TestSkillRepository:
    def test_list_empty(self):
        db = _make_db()
        repo = SkillRepository(db)
        assert repo.list_all() == []

    def test_save_and_get(self):
        db = _make_db()
        repo = SkillRepository(db)
        skill = Skill(name="coder", description="コードを書く", content="You are a coder.")
        saved = repo.save(skill)
        assert saved.id is not None
        assert saved.name == "coder"
        loaded = repo.get("coder")
        assert loaded is not None
        assert loaded.name == "coder"
        assert loaded.description == "コードを書く"
        assert loaded.content == "You are a coder."

    def test_get_nonexistent(self):
        db = _make_db()
        repo = SkillRepository(db)
        assert repo.get("nonexistent") is None

    def test_list_all(self):
        db = _make_db()
        repo = SkillRepository(db)
        repo.save(Skill(name="skill_b", content="b"))
        repo.save(Skill(name="skill_a", content="a"))
        skills = repo.list_all()
        assert len(skills) == 2
        # sorted by name
        assert skills[0].name == "skill_a"
        assert skills[1].name == "skill_b"

    def test_save_update(self):
        db = _make_db()
        repo = SkillRepository(db)
        saved = repo.save(Skill(name="x", content="old"))
        updated = repo.save(Skill(id=saved.id, name="x", content="new", created_at=saved.created_at))
        assert updated.content == "new"
        loaded = repo.get("x")
        assert loaded is not None
        assert loaded.content == "new"

    def test_upsert_creates_new(self):
        db = _make_db()
        repo = SkillRepository(db)
        saved = repo.upsert(Skill(name="newskill", content="hello"))
        assert saved.id is not None
        assert repo.get("newskill") is not None

    def test_upsert_updates_existing(self):
        db = _make_db()
        repo = SkillRepository(db)
        repo.save(Skill(name="existing", content="old"))
        repo.upsert(Skill(name="existing", content="updated"))
        loaded = repo.get("existing")
        assert loaded is not None
        assert loaded.content == "updated"

    def test_delete(self):
        db = _make_db()
        repo = SkillRepository(db)
        repo.save(Skill(name="todelete", content="bye"))
        repo.delete("todelete")
        assert repo.get("todelete") is None

    def test_delete_nonexistent_no_error(self):
        db = _make_db()
        repo = SkillRepository(db)
        repo.delete("doesnotexist")  # should not raise
