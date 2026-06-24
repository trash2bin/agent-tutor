"""Репозиторий студентов + расписание групп."""

from __future__ import annotations

import json
from typing import Any

from agent_tutor_sdk.db.models import ScheduleEntry, Student
from agent_tutor_sdk.db.repositories.base import BaseRepository
from agent_tutor_sdk.db.repositories.group_repo import GroupRepo


class StudentRepo(BaseRepository):
    """Репозиторий для студентов и расписания их групп."""

    def __init__(self, connector, group_repo: GroupRepo | None = None) -> None:
        super().__init__(connector)
        self._group_repo = group_repo or GroupRepo(connector)

    def get_student(self, student_id: str) -> Student | None:
        """Получить студента по ID."""
        row = self.fetch_one("SELECT * FROM students WHERE id = ?", (student_id,))
        return self._student_from_row(row) if row else None

    def get_id_student(self, name: str | None) -> Student | None:
        """Найти студента по полному имени."""
        if name is None:
            return None
        row = self.fetch_one("SELECT * FROM students WHERE name = ?", (name,))
        return self._student_from_row(row) if row else None

    def get_schedule(
        self, group_id: str, day: str | None = None
    ) -> list[ScheduleEntry]:
        """Расписание группы."""
        if day:
            rows = self.fetch_all(
                "SELECT * FROM schedule WHERE group_id = ? AND day = ?",
                (group_id, day),
            )
        else:
            rows = self.fetch_all(
                "SELECT * FROM schedule WHERE group_id = ?",
                (group_id,),
            )
        return [self._schedule_entry_from_row(row) for row in rows]

    def _student_from_row(self, row: Any) -> Student:
        return Student(
            id=row["id"],
            name=row["name"],
            group=self._group_repo.get_group(row["group_id"]),
            course=row["course"],
        )

    def _schedule_entry_from_row(self, row: Any) -> ScheduleEntry:
        lessons = [
            self.lesson_from_dict(lesson)
            for lesson in json.loads(row["lessons_json"] or "[]")
        ]
        return ScheduleEntry(
            id=row["id"],
            group=self._group_repo.get_group(row["group_id"]),
            day=row["day"],
            lessons=lessons,
        )
