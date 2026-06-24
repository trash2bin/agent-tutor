"""Базовый репозиторий — execute/fetch/lesson_from_dict.

Содержит общую логику переоткрытия соединения при OperationalError
(потеря связи с PostgreSQL / таймаут).
"""

from __future__ import annotations

import logging
from typing import Any

from agent_tutor_sdk.db.connector import Connector, is_operational_error
from agent_tutor_sdk.db.models import Lesson

logger = logging.getLogger(__name__)


class BaseRepository:
    """Базовый репозиторий с доступом к соединению БД."""

    def __init__(self, connector: Connector) -> None:
        self.connector = connector

    @property
    def conn(self) -> Any:
        return self.connector.connection

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> Any:
        adapted = self.connector.adapt_sql(sql)
        try:
            cursor = self.conn.cursor()
            cursor.execute(adapted, parameters)
            return cursor
        except Exception as exc:
            # OperationalError — соединение могло умереть. Сбрасываем и пробрасываем.
            if is_operational_error(exc) and hasattr(
                self.connector, "reset_thread_connection"
            ):
                logger.warning("DB connection lost, resetting: %s", exc)
                self.connector.reset_thread_connection()  # type: ignore[attr-defined]
            raise

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
