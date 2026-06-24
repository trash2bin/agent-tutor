"""Репозитории для доменных сущностей БД.

Каждый репозиторий работает через Connector и содержит
только методы своей предметной области.
"""

from agent_tutor_sdk.db.repositories.base import BaseRepository
from agent_tutor_sdk.db.repositories.discipline_repo import DisciplineRepo
from agent_tutor_sdk.db.repositories.grade_repo import GradeRepo
from agent_tutor_sdk.db.repositories.group_repo import GroupRepo
from agent_tutor_sdk.db.repositories.student_repo import StudentRepo
from agent_tutor_sdk.db.repositories.teacher_repo import TeacherRepo

__all__ = [
    "BaseRepository",
    "GroupRepo",
    "StudentRepo",
    "TeacherRepo",
    "GradeRepo",
    "DisciplineRepo",
]
