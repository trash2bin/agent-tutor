"""Репозиторий преподавателей и их расписания."""

from __future__ import annotations

import json
from typing import Any

from agent_tutor_sdk.db.models import ScheduleEntry, Teacher
from agent_tutor_sdk.db.repositories.base import BaseRepository
from agent_tutor_sdk.db.repositories.group_repo import GroupRepo


class TeacherRepo(BaseRepository):
    """Репозиторий для преподавателей и их расписания."""

    def __init__(self, connector, group_repo: GroupRepo | None = None) -> None:
        super().__init__(connector)
        self._group_repo = group_repo or GroupRepo(connector)

    def get_teacher_by_name(self, name: str) -> Teacher | None:
        """Найти преподавателя по имени."""
        row = self.fetch_one("SELECT * FROM teachers WHERE name = ?", (name,))
        if not row:
            return None
        return Teacher(
            id=row["id"],
            name=row["name"],
            disciplines=json.loads(row["disciplines_json"] or "[]"),
        )

    def get_teacher_schedule(
        self, teacher_name: str, day: str | None = None
    ) -> list[ScheduleEntry]:
        """Расписание преподавателя."""
        teacher = self.get_teacher_by_name(teacher_name)
        if not teacher:
            return []

        sql = "SELECT * FROM schedule"
        params: list[Any] = []
        if day:
            sql += " WHERE day = ?"
            params.append(day)

        entries: list[ScheduleEntry] = []
        for row in self.fetch_all(sql, params):
            lessons_data = json.loads(row["lessons_json"] or "[]")
            teacher_lessons = [
                self.lesson_from_dict(lesson)
                for lesson in lessons_data
                if lesson.get("teacher_name") == teacher_name
            ]

            if teacher_lessons:
                entries.append(
                    ScheduleEntry(
                        id=row["id"],
                        group=self._group_repo.get_group(row["group_id"]),
                        day=row["day"],
                        lessons=teacher_lessons,
                    )
                )
        return entries
