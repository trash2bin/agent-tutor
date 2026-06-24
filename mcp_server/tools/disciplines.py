"""Инструменты для работы с дисциплинами и учебными материалами."""

from __future__ import annotations


from agent_tutor_sdk.db.database import Database
from agent_tutor_sdk.db.models import Discipline


class DisciplineTools:
    def __init__(self, db: Database):
        self.db = db

    def get_disciplines(self, student_id: str) -> list[Discipline]:
        """Get disciplines for a student."""
        return self.db.get_disciplines(student_id)
