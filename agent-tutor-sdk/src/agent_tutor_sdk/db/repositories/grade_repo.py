"""Репозиторий оценок студентов."""

from __future__ import annotations

from typing import Any

from agent_tutor_sdk.db.models import Grade
from agent_tutor_sdk.db.repositories.base import BaseRepository


class GradeRepo(BaseRepository):
    """Репозиторий для работы с оценками."""

    def get_student_grades(
        self, student_id: str, discipline_id: str | None = None
    ) -> list[Grade]:
        """Оценки студента, опционально отфильтрованные по дисциплине."""
        sql = """
            SELECT
                grades.id,
                grades.student_id,
                grades.discipline_id,
                disciplines.name AS discipline_name,
                grades.grade,
                grades.date
            FROM grades
            LEFT JOIN disciplines ON disciplines.id = grades.discipline_id
            WHERE grades.student_id = ?
        """
        params: list[Any] = [student_id]
        if discipline_id:
            sql += " AND grades.discipline_id = ?"
            params.append(discipline_id)
        sql += " ORDER BY grades.date DESC, disciplines.name ASC"
        return [self._grade_from_row(row) for row in self.fetch_all(sql, params)]

    @staticmethod
    def _grade_from_row(row: Any) -> Grade:
        return Grade(
            id=row["id"],
            student_id=row["student_id"],
            discipline_id=row["discipline_id"],
            discipline_name=row["discipline_name"] or "Неизвестная дисциплина",
            grade=row["grade"],
            date=row["date"],
        )
