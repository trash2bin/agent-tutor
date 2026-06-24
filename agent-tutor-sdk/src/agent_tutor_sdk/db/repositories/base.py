"""Базовый репозиторий — execute/fetch/lesson_from_dict."""

from __future__ import annotations

from typing import Any

from agent_tutor_sdk.db.connector import Connector
from agent_tutor_sdk.db.models import Lesson


class BaseRepository:
    """Базовый репозиторий с доступом к соединению БД."""

    def __init__(self, connector: Connector) -> None:
        self.connector = connector

    @property
    def conn(self) -> Any:
        return self.connector.connection

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> Any:
        adapted = self.connector.adapt_sql(sql)
        cursor = self.conn.cursor()
        cursor.execute(adapted, parameters)
        return cursor

    def fetch_one(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> Any:
        return self.execute(sql, parameters).fetchone()

    def fetch_all(
        self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()
    ) -> list[Any]:
        return self.execute(sql, parameters).fetchall()

    @staticmethod
    def lesson_from_dict(lesson: dict[str, Any]) -> Lesson:
        """Создать Lesson из словаря JSON-поля lessons_json."""
        return Lesson(
            discipline_id=lesson["discipline_id"],
            discipline_name=lesson.get("discipline_name", "Неизвестно"),
            teacher_name=lesson["teacher_name"],
            room=lesson["room"],
        )
