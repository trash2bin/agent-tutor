"""Загрузка тестовых данных (фикстур) из fixtures.json.

Диалект SQL — общий для SQLite (3.24+) и PostgreSQL:
  INSERT INTO … VALUES (…) ON CONFLICT DO NOTHING
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

INSERT_GROUP = (
    "INSERT INTO groups (id, name, speciality) VALUES (?, ?, ?) ON CONFLICT DO NOTHING"
)
INSERT_STUDENT = "INSERT INTO students (id, name, group_id, course) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"
INSERT_TEACHER = "INSERT INTO teachers (id, name, disciplines_json) VALUES (?, ?, ?) ON CONFLICT DO NOTHING"
INSERT_DISCIPLINE = "INSERT INTO disciplines (id, name, description) VALUES (?, ?, ?) ON CONFLICT DO NOTHING"
INSERT_MATERIAL = "INSERT INTO materials (id, discipline_id, type, content) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"
INSERT_GRADE = "INSERT INTO grades (id, student_id, discipline_id, grade, date) VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING"
INSERT_SCHEDULE = "INSERT INTO schedule (id, group_id, day, lessons_json) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING"


def load_fixtures(
    connection: Any, fixtures_path: Path, *, adapter: Callable[[str], str] | None = None
) -> None:
    """Загрузить фикстуры из JSON-файла.

    Args:
        connection: DBAPI2-совместимое соединение
        fixtures_path: путь к fixtures.json
        adapter: функция adapt_sql(sql) — подставляет параметрический стиль
    """
    if not fixtures_path.exists():
        logger.warning("Fixtures file not found: %s", fixtures_path)
        return

    data = json.loads(fixtures_path.read_text(encoding="utf-8"))

    _insert_many(
        connection,
        INSERT_GROUP,
        adapter,
        (
            (group["id"], group["name"], group["specialty"])
            for group in data.get("groups", [])
        ),
    )
    _insert_many(
        connection,
        INSERT_STUDENT,
        adapter,
        (
            (student["id"], student["name"], student["group_id"], student["course"])
            for student in data.get("students", [])
        ),
    )
    _insert_many(
        connection,
        INSERT_TEACHER,
        adapter,
        (
            (
                teacher["id"],
                teacher["name"],
                json.dumps(teacher["disciplines"], ensure_ascii=False),
            )
            for teacher in data.get("teachers", [])
        ),
    )
    _insert_many(
        connection,
        INSERT_DISCIPLINE,
        adapter,
        (
            (discipline["id"], discipline["name"], discipline["description"])
            for discipline in data.get("disciplines", [])
        ),
    )
    _insert_many(
        connection,
        INSERT_MATERIAL,
        adapter,
        (
            (
                material["id"],
                material["discipline_id"],
                material["type"],
                material["content"],
            )
            for material in data.get("materials", [])
        ),
    )
    _insert_many(
        connection,
        INSERT_GRADE,
        adapter,
        (
            (
                grade["id"],
                grade["student_id"],
                grade["discipline_id"],
                str(grade["grade"]),
                grade["date"],
            )
            for grade in data.get("grades", [])
        ),
    )
    _insert_many(
        connection,
        INSERT_SCHEDULE,
        adapter,
        (
            (
                entry["id"],
                entry["group_id"],
                entry["day"],
                json.dumps(entry["lessons"], ensure_ascii=False),
            )
            for entry in data.get("schedule", [])
        ),
    )
    connection.commit()


def _insert_many(
    connection: Any, sql: str, adapter: Callable[[str], str] | None, rows: Any
) -> None:
    if adapter:
        sql = adapter(sql)
    cursor = connection.cursor()
    cursor.executemany(sql, rows)
    cursor.close()
