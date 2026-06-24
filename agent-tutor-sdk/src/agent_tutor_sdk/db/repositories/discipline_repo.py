"""Репозиторий дисциплин."""

from __future__ import annotations

import json

from agent_tutor_sdk.db.models import Discipline
from agent_tutor_sdk.db.repositories.base import BaseRepository


class DisciplineRepo(BaseRepository):
    """Репозиторий для работы с дисциплинами."""

    def get_disciplines(self, student_id: str) -> list[Discipline]:
        """Дисциплины студента (через группу → расписание)."""
        row = self.fetch_one(
            "SELECT group_id FROM students WHERE id = ?", (student_id,)
        )
        if not row:
            return []

        discipline_ids = self._discipline_ids_for_group(row["group_id"])
        if not discipline_ids:
            return []

        placeholders = ", ".join("?" * len(discipline_ids))
        rows = self.fetch_all(
            f"SELECT * FROM disciplines WHERE id IN ({placeholders}) ORDER BY name ASC",
            sorted(discipline_ids),
        )
        return [self._discipline_from_row(row) for row in rows]

    def get_discipline(self, discipline_id: str) -> Discipline | None:
        """Получить дисциплину по ID."""
        row = self.fetch_one("SELECT * FROM disciplines WHERE id = ?", (discipline_id,))
        return self._discipline_from_row(row) if row else None

    def get_all_disciplines(self) -> list[Discipline]:
        """Все дисциплины."""
        return [
            self._discipline_from_row(row)
            for row in self.fetch_all("SELECT * FROM disciplines ORDER BY name ASC")
        ]

    @staticmethod
    def _discipline_from_row(row) -> Discipline:
        return Discipline(
            id=row["id"],
            name=row["name"],
            description=row["description"],
        )

    def _discipline_ids_for_group(self, group_id: str) -> set[str]:
        """Уникальные ID дисциплин из расписания группы."""
        rows = self.fetch_all(
            "SELECT lessons_json FROM schedule WHERE group_id = ?", (group_id,)
        )
        discipline_ids: set[str] = set()
        for row in rows:
            for lesson in json.loads(row["lessons_json"] or "[]"):
                d_id = lesson.get("discipline_id")
                if d_id:
                    discipline_ids.add(d_id)
        return discipline_ids
