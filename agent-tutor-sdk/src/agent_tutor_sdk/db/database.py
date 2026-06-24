"""Фасад БД — абстрагирован от конкретного движка (SQLite / PostgreSQL).

Через Database.get_db() возвращается синглтон, работающий либо с SQLite
(no DATABASE_URL), либо с PostgreSQL (DATABASE_URL задана).

Делегирует доменные запросы в специализированные репозитории.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from agent_tutor_sdk.db.connector import (
    PROJECT_ROOT,
    Connector,
    create_connector,
    is_operational_error,
)
from agent_tutor_sdk.db.fixtures import load_fixtures
from agent_tutor_sdk.db.schema import create_schema

from .models import (
    Discipline,
    Grade,
    Group,
    ScheduleEntry,
    Student,
    Teacher,
)
from .repositories import (
    DisciplineRepo,
    GradeRepo,
    GroupRepo,
    StudentRepo,
    TeacherRepo,
)

logger = logging.getLogger(__name__)

FIXTURES_PATH = PROJECT_ROOT / "fixtures.json"

# Глобальный экземпляр (ленивый, thread-safe через RLock)
_db_instance: Database | None = None
_db_lock = threading.RLock()


def get_db(load_seed_data: bool | None = None) -> Database:
    """Получить (или создать) глобальный экземпляр Database.

    Args:
        load_seed_data: Явно указать, загружать ли фикстуры.
            None (по умолчанию) — авто-определение: загружаются только
            если БД пустая. True — принудительно. False — не загружать.
    """
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = Database(load_seed_data=load_seed_data)
    return _db_instance


def reset_db() -> None:
    """Сбросить глобальный экземпляр (для тестов)."""
    global _db_instance
    with _db_lock:
        if _db_instance is not None:
            _db_instance.close()
            _db_instance = None


class Database:
    """Application database facade over a managed connector.

    Делегирует доменные запросы в специализированные репозитории.
    Сохраняет execute/fetch_one/fetch_all для прямого SQL-доступа (fixtures, demo).
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        connector: Connector | None = None,
        load_seed_data: bool | None = None,
        database_url: str | None = None,
    ) -> None:
        """Create Database instance.

        Args:
            db_path: путь к SQLite-файлу
            connector: готовый коннектор (если уже есть)
            load_seed_data: загружать ли seed-данные (fixtures.json).
                None (по умолчанию) — авто: загружаем только если БД пустая.
                True — принудительно.
                False — не загружать.
            database_url: PostgreSQL DSN (альтернатива db_path)
        """
        self.connector = connector or create_connector(database_url, db_path)
        self.conn = self.connector.connection
        self._closed = False
        self._adapt = self.connector.adapt_sql

        # Инициализация репозиториев
        self.group_repo = GroupRepo(self.connector)
        self.student_repo = StudentRepo(self.connector, group_repo=self.group_repo)
        self.teacher_repo = TeacherRepo(self.connector, group_repo=self.group_repo)
        self.grade_repo = GradeRepo(self.connector)
        self.discipline_repo = DisciplineRepo(self.connector)

        # Schema всегда создаётся (CREATE TABLE IF NOT EXISTS — идемпотентно)
        create_schema(self.conn, adapter=self._adapt)

        # Авто-определение: загружаем фикстуры только если БД пустая
        if load_seed_data is None:
            if self._has_data():
                logger.info("Database already has data — skipping seed fixtures")
            else:
                logger.info("Empty database — loading seed fixtures")
                load_fixtures(self.conn, FIXTURES_PATH, adapter=self._adapt)
        elif load_seed_data:
            load_fixtures(self.conn, FIXTURES_PATH, adapter=self._adapt)

    @property
    def db_path(self) -> str:
        if hasattr(self.connector, "db_path"):
            return str(self.connector.db_path)  # type: ignore[union-attr]
        return self.connector.database_url  # type: ignore[union-attr]

    # ── raw SQL helpers ──────────────────────────────────────────────

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> Any:
        """Запустить SQL и вернуть курсор."""
        adapted = self._adapt(sql)
        try:
            cursor = self.conn.cursor()
            cursor.execute(adapted, parameters)
            return cursor
        except Exception as exc:
            if is_operational_error(exc) and hasattr(
                self.connector, "reset_thread_connection"
            ):
                logger.warning(
                    "DB connection lost in Database.execute, resetting: %s", exc
                )
                self.connector.reset_thread_connection()  # type: ignore[attr-defined]
            raise

    def fetch_one(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> Any:
        return self.execute(sql, parameters).fetchone()

    def fetch_all(
        self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()
    ) -> list[Any]:
        return self.execute(sql, parameters).fetchall()

    # ── domain methods (делегированы репозиториям) ───────────────────

    def get_group(self, group_id: str) -> Group | None:
        """Получить группу по ID."""
        return self.group_repo.get_group(group_id)

    def get_student(self, student_id: str) -> Student | None:
        """Получить студента по ID."""
        return self.student_repo.get_student(student_id)

    def get_id_student(self, name: str | None) -> Student | None:
        """Найти студента по полному имени."""
        return self.student_repo.get_id_student(name)

    def get_teacher_by_name(self, name: str) -> Teacher | None:
        """Найти преподавателя по имени."""
        return self.teacher_repo.get_teacher_by_name(name)

    def get_teacher_schedule(
        self, teacher_name: str, day: str | None = None
    ) -> list[ScheduleEntry]:
        """Расписание преподавателя."""
        return self.teacher_repo.get_teacher_schedule(teacher_name, day)

    def get_schedule(
        self, group_id: str, day: str | None = None
    ) -> list[ScheduleEntry]:
        """Расписание группы."""
        return self.student_repo.get_schedule(group_id, day)

    def get_disciplines(self, student_id: str) -> list[Discipline]:
        """Список дисциплин студента."""
        return self.discipline_repo.get_disciplines(student_id)

    def get_discipline(self, discipline_id: str) -> Discipline | None:
        """Получить дисциплину по ID."""
        return self.discipline_repo.get_discipline(discipline_id)

    def get_all_disciplines(self) -> list[Discipline]:
        """Все дисциплины."""
        return self.discipline_repo.get_all_disciplines()

    def get_student_grades(
        self, student_id: str, discipline_id: str | None = None
    ) -> list[Grade]:
        """Оценки студента."""
        return self.grade_repo.get_student_grades(student_id, discipline_id)

    # ── helpers ─────────────────────────────────────────────────────

    def _has_data(self) -> bool:
        """Проверить, есть ли данные в таблицах.

        Работает с SQLite (sqlite3.Row) и PostgreSQL (RealDictCursor).
        Возвращает True, если хотя бы одна из основных таблиц не пуста.
        """
        for table in ("groups", "students", "teachers", "disciplines"):
            try:
                cursor = self.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                row = cursor.fetchone()
                if row is not None:
                    cnt = row["cnt"] if hasattr(row, "keys") else row[0]
                    if cnt and int(cnt) > 0:
                        return True
            except Exception:
                # Таблицы может не быть — это не ошибка
                pass
        return False

    # ── lifecycle ────────────────────────────────────────────────────

    def ping(self) -> None:
        try:
            self.execute("SELECT 1")
        except Exception as exc:
            if is_operational_error(exc) and hasattr(
                self.connector, "reset_thread_connection"
            ):
                self.connector.reset_thread_connection()  # type: ignore[attr-defined]
            raise

    def commit(self) -> None:
        try:
            self.conn.commit()
        except Exception as exc:
            if is_operational_error(exc) and hasattr(
                self.connector, "reset_thread_connection"
            ):
                self.connector.reset_thread_connection()  # type: ignore[attr-defined]
            raise

    def rollback(self) -> None:
        try:
            self.conn.rollback()
        except Exception as exc:
            if is_operational_error(exc) and hasattr(
                self.connector, "reset_thread_connection"
            ):
                self.connector.reset_thread_connection()  # type: ignore[attr-defined]
            raise

    def close(self) -> None:
        if not self._closed:
            self.connector.close()
            self._closed = True

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False
