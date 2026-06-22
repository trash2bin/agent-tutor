"""Фасад БД — абстрагирован от конкретного движка (SQLite / PostgreSQL).

Через Database.get_db() возвращается синглтон, работающий либо с SQLite
(no DATABASE_URL), либо с PostgreSQL (DATABASE_URL задана).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from db.connector import (
    PROJECT_ROOT,
    Connector,
    create_connector,
)
from db.fixtures import load_fixtures
from db.schema import create_schema

from .models import Discipline, Grade, Group, Lesson, ScheduleEntry, Student, Teacher

FIXTURES_PATH = PROJECT_ROOT / "fixtures.json"

# Глобальный экземпляр (ленивый, thread-safe через RLock)
_db_instance: Database | None = None
_db_lock = __import__("threading").RLock()


def get_db() -> Database:
    """Получить (или создать) глобальный экземпляр Database."""
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = Database()
    return _db_instance


def reset_db() -> None:
    """Сбросить глобальный экземпляр (для тестов)."""
    global _db_instance
    with _db_lock:
        if _db_instance is not None:
            _db_instance.close()
            _db_instance = None


class Database:
    """Application database facade over a managed connector."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        connector: Connector | None = None,
        load_seed_data: bool = True,
        database_url: str | None = None,
    ) -> None:
        self.connector = connector or create_connector(database_url, db_path)
        self.conn = self.connector.connection
        self._closed = False
        self._adapt: Callable[[str], str] = self.connector.adapt_sql

        create_schema(self.conn, adapter=self._adapt)
        if load_seed_data:
            load_fixtures(self.conn, FIXTURES_PATH, adapter=self._adapt)

    @property
    def db_path(self) -> str:
        if hasattr(self.connector, "db_path"):
            return str(self.connector.db_path)  # type: ignore[union-attr]
        return self.connector.database_url  # type: ignore[union-attr]

    # ── raw helpers ──────────────────────────────────────────────────

    def execute(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> Any:
        """Запустить SQL и вернуть курсор.

        sqlite3.Connection.execute() возвращает курсор напрямую.
        psycopg2.Connection.execute() не существует — создаём курсор явно.
        """
        adapted = self._adapt(sql)
        cursor = self.conn.cursor()
        cursor.execute(adapted, parameters)
        return cursor

    def fetch_one(self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()) -> Any:
        return self.execute(sql, parameters).fetchone()

    def fetch_all(
        self, sql: str, parameters: tuple[Any, ...] | list[Any] = ()
    ) -> list[Any]:
        return self.execute(sql, parameters).fetchall()

    # ── domain methods ───────────────────────────────────────────────

    def get_group(self, group_id: str) -> Group | None:
        row = self.fetch_one("SELECT * FROM groups WHERE id = ?", (group_id,))
        if not row:
            return None
        return Group(
            id=row["id"],
            name=row["name"],
            speciality=row["speciality"],
        )

    def get_student(self, student_id: str) -> Student | None:
        row = self.fetch_one("SELECT * FROM students WHERE id = ?", (student_id,))
        return self._student_from_row(row) if row else None

    def get_id_student(self, name: str | None) -> Student | None:
        if name is None:
            return None
        row = self.fetch_one("SELECT * FROM students WHERE name = ?", (name,))
        return self._student_from_row(row) if row else None

    def get_teacher_by_name(self, name: str) -> Teacher | None:
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
                self._lesson_from_dict(lesson)
                for lesson in lessons_data
                if lesson.get("teacher_name") == teacher_name
            ]

            if teacher_lessons:
                entries.append(
                    ScheduleEntry(
                        id=row["id"],
                        group=self.get_group(row["group_id"]),
                        day=row["day"],
                        lessons=teacher_lessons,
                    )
                )
        return entries

    def get_schedule(
        self, group_id: str, day: str | None = None
    ) -> list[ScheduleEntry]:
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

    def get_disciplines(self, student_id: str) -> list[Discipline]:
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
        row = self.fetch_one("SELECT * FROM disciplines WHERE id = ?", (discipline_id,))
        return self._discipline_from_row(row) if row else None

    def get_all_disciplines(self) -> list[Discipline]:
        return [
            self._discipline_from_row(row)
            for row in self.fetch_all("SELECT * FROM disciplines ORDER BY name ASC")
        ]

    def get_student_grades(
        self, student_id: str, discipline_id: str | None = None
    ) -> list[Grade]:
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

    def ping(self) -> None:
        self.execute("SELECT 1")

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        if not self._closed:
            self.connector.close()
            self._closed = True

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    # ── internal helpers ─────────────────────────────────────────────

    def _student_from_row(self, row: Any) -> Student:
        return Student(
            id=row["id"],
            name=row["name"],
            group=self.get_group(row["group_id"]),
            course=row["course"],
        )

    def _discipline_ids_for_group(self, group_id: str) -> set[str]:
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

    def _schedule_entry_from_row(self, row: Any) -> ScheduleEntry:
        lessons = [
            self._lesson_from_dict(lesson)
            for lesson in json.loads(row["lessons_json"] or "[]")
        ]
        return ScheduleEntry(
            id=row["id"],
            group=self.get_group(row["group_id"]),
            day=row["day"],
            lessons=lessons,
        )

    @staticmethod
    def _lesson_from_dict(lesson: dict[str, Any]) -> Lesson:
        return Lesson(
            discipline_id=lesson["discipline_id"],
            discipline_name=lesson.get("discipline_name", "Неизвестно"),
            teacher_name=lesson["teacher_name"],
            room=lesson["room"],
        )

    @staticmethod
    def _discipline_from_row(row: Any) -> Discipline:
        return Discipline(
            id=row["id"],
            name=row["name"],
            description=row["description"],
        )

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
