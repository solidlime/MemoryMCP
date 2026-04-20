from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from memory_mcp.domain.shared.time_utils import format_iso, get_now

if TYPE_CHECKING:
    import sqlite3


class Skill(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    content: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class SkillRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def list_all(self) -> list[Skill]:
        rows = self._db.execute(
            "SELECT id, name, description, content, created_at, updated_at FROM skills ORDER BY name"
        ).fetchall()
        return [Skill(id=r[0], name=r[1], description=r[2] or "", content=r[3] or "", created_at=r[4], updated_at=r[5]) for r in rows]

    def get(self, name: str) -> Skill | None:
        row = self._db.execute(
            "SELECT id, name, description, content, created_at, updated_at FROM skills WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return Skill(id=row[0], name=row[1], description=row[2] or "", content=row[3] or "", created_at=row[4], updated_at=row[5])

    def save(self, skill: Skill) -> Skill:
        now = format_iso(get_now())
        if skill.id is None:
            cursor = self._db.execute(
                "INSERT INTO skills (name, description, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (skill.name, skill.description, skill.content, now, now),
            )
            self._db.commit()
            return Skill(id=cursor.lastrowid, name=skill.name, description=skill.description, content=skill.content, created_at=now, updated_at=now)
        else:
            self._db.execute(
                "UPDATE skills SET name=?, description=?, content=?, updated_at=? WHERE id=?",
                (skill.name, skill.description, skill.content, now, skill.id),
            )
            self._db.commit()
            return Skill(id=skill.id, name=skill.name, description=skill.description, content=skill.content, created_at=skill.created_at, updated_at=now)

    def upsert(self, skill: Skill) -> Skill:
        now = format_iso(get_now())
        existing = self.get(skill.name)
        if existing is None:
            cursor = self._db.execute(
                "INSERT INTO skills (name, description, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (skill.name, skill.description, skill.content, now, now),
            )
            self._db.commit()
            return Skill(id=cursor.lastrowid, name=skill.name, description=skill.description, content=skill.content, created_at=now, updated_at=now)
        else:
            self._db.execute(
                "UPDATE skills SET description=?, content=?, updated_at=? WHERE name=?",
                (skill.description, skill.content, now, skill.name),
            )
            self._db.commit()
            return Skill(id=existing.id, name=skill.name, description=skill.description, content=skill.content, created_at=existing.created_at, updated_at=now)

    def delete(self, name: str) -> None:
        self._db.execute("DELETE FROM skills WHERE name = ?", (name,))
        self._db.commit()
