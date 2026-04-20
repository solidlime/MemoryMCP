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
        return [
            Skill(id=r[0], name=r[1], description=r[2] or "", content=r[3] or "", created_at=r[4], updated_at=r[5])
            for r in rows
        ]

    def get(self, name: str) -> Skill | None:
        row = self._db.execute(
            "SELECT id, name, description, content, created_at, updated_at FROM skills WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return Skill(
            id=row[0], name=row[1], description=row[2] or "", content=row[3] or "", created_at=row[4], updated_at=row[5]
        )

    def save(self, skill: Skill) -> Skill:
        now = format_iso(get_now())
        if skill.id is None:
            cursor = self._db.execute(
                "INSERT INTO skills (name, description, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (skill.name, skill.description, skill.content, now, now),
            )
            self._db.commit()
            return Skill(
                id=cursor.lastrowid,
                name=skill.name,
                description=skill.description,
                content=skill.content,
                created_at=now,
                updated_at=now,
            )
        else:
            self._db.execute(
                "UPDATE skills SET name=?, description=?, content=?, updated_at=? WHERE id=?",
                (skill.name, skill.description, skill.content, now, skill.id),
            )
            self._db.commit()
            return Skill(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                content=skill.content,
                created_at=skill.created_at,
                updated_at=now,
            )

    def upsert(self, skill: Skill) -> Skill:
        now = format_iso(get_now())
        existing = self.get(skill.name)
        if existing is None:
            cursor = self._db.execute(
                "INSERT INTO skills (name, description, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (skill.name, skill.description, skill.content, now, now),
            )
            self._db.commit()
            return Skill(
                id=cursor.lastrowid,
                name=skill.name,
                description=skill.description,
                content=skill.content,
                created_at=now,
                updated_at=now,
            )
        else:
            self._db.execute(
                "UPDATE skills SET description=?, content=?, updated_at=? WHERE name=?",
                (skill.description, skill.content, now, skill.name),
            )
            self._db.commit()
            return Skill(
                id=existing.id,
                name=skill.name,
                description=skill.description,
                content=skill.content,
                created_at=existing.created_at,
                updated_at=now,
            )

    def delete(self, name: str) -> None:
        self._db.execute("DELETE FROM skills WHERE name = ?", (name,))
        self._db.commit()

    def load_from_dir(self, skills_dir: str | None = None) -> list[Skill]:
        """Scan <skills_dir>/<name>/SKILL.md files and upsert them into the DB.

        Frontmatter (---block---) may contain `name` and `description` fields.
        The rest of the file becomes the system-prompt `content`.
        If no frontmatter is present the directory name is used as the skill name.
        """
        from pathlib import Path

        if skills_dir is None:
            from memory_mcp.config.settings import get_settings

            skills_dir = get_settings().skills_dir

        base = Path(skills_dir)
        if not base.exists():
            return []

        upserted: list[Skill] = []
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            skill_file = entry / "SKILL.md"
            if not skill_file.exists():
                continue
            raw = skill_file.read_text(encoding="utf-8")
            name, description, content = _parse_skill_md(entry.name, raw)
            upserted.append(self.upsert(Skill(name=name, description=description, content=content)))
        return upserted


def _parse_skill_md(dir_name: str, raw: str) -> tuple[str, str, str]:
    """Extract name/description from YAML frontmatter, body as content."""
    name = dir_name
    description = ""
    body = raw
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            fm = raw[3:end].strip()
            body = raw[end + 3 :].strip()
            for line in fm.splitlines():
                if line.startswith("name:"):
                    name = line[5:].strip()
                elif line.startswith("description:"):
                    description = line[12:].strip()
    return name, description, body
