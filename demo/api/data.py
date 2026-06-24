from __future__ import annotations

import json
from typing import Any

from agent_tutor_sdk.db.database import get_db


class DemoDataRepository:
    """Repository for demo data access.

    Инициализируется лениво — БД подключается только при первом вызове метода.
    Это позволяет:
      - не зависеть от доступности БД при импорте модуля
      - подменять окружение до первого обращения
      - использовать в тестах без поднятой БД
    """

    def __init__(self) -> None:
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def overview(self) -> dict[str, Any]:
        """Get an overview of all demo data."""
        return {
            "stats": self._stats(),
            "students": self._students(),
            "teachers": self._teachers(),
            "disciplines": self._disciplines(),
            "schedule": self._schedule(),
            "documents": self._documents(),
            "grades": self._grades(),
        }

    def _stats(self) -> dict[str, int]:
        names = [
            "students",
            "teachers",
            "disciplines",
            "documents",
            "grades",
            "schedule",
        ]
        return {name: self._count(name) for name in names}

    def _count(self, table: str) -> int:
        if table not in {
            "students",
            "teachers",
            "disciplines",
            "documents",
            "grades",
            "schedule",
        }:
            raise ValueError(f"Unsupported stats table: {table}")

        fetch = self.db.fetch_one(f"SELECT COUNT(*) AS total FROM {table}")

        if fetch is None:
            raise RuntimeError(f"Failed to fetch count for table: {table}")

        return fetch["total"]

    def _students(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT students.id, students.name, students.course,
                   groups.name AS group_name, groups.speciality
            FROM students
            LEFT JOIN groups ON groups.id = students.group_id
            ORDER BY groups.name, students.name
            """
        )
        return [dict(row) for row in rows]

    def _teachers(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT id, name, disciplines_json FROM teachers ORDER BY name"
        )
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "disciplines": json.loads(row["disciplines_json"] or "[]"),
            }
            for row in rows
        ]

    def _disciplines(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT id, name, description FROM disciplines ORDER BY name"
        )
        return [dict(row) for row in rows]

    def _schedule(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT schedule.id, schedule.day, groups.name AS group_name, schedule.lessons_json
            FROM schedule
            LEFT JOIN groups ON groups.id = schedule.group_id
            ORDER BY groups.name, schedule.day
            """
        )
        return [
            {
                "id": row["id"],
                "day": row["day"],
                "group_name": row["group_name"],
                "lessons": json.loads(row["lessons_json"] or "[]"),
            }
            for row in rows
        ]

    def _documents(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT documents.id, documents.title, documents.source_path,
                   documents.mime_type, documents.discipline_id,
                   disciplines.name AS discipline_name, documents.created_at
            FROM documents
            LEFT JOIN disciplines ON disciplines.id = documents.discipline_id
            ORDER BY documents.created_at DESC
            LIMIT 40
            """
        )
        return [dict(row) for row in rows]

    def _grades(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT grades.id, students.name AS student_name,
                   disciplines.name AS discipline_name, grades.grade, grades.date
            FROM grades
            LEFT JOIN students ON students.id = grades.student_id
            LEFT JOIN disciplines ON disciplines.id = grades.discipline_id
            ORDER BY grades.date DESC
            LIMIT 80
            """
        )
        return [dict(row) for row in rows]


# Global data repository instance (lazy — init at first use)
data_repository = DemoDataRepository()
