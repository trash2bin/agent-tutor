"""DB-connector: абстракция над DBAPI2 (SQLite / PostgreSQL).

Позволяет переключать бэкенд через DATABASE_URL:
  - не задана → SQLite (локальная universtity.db)
  - postgresql://... → PostgreSQL (Docker или внешний)
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "university.db"

# ──────────────────────────────────────────────────────────────────────
# DBAPI2 protocol — минимальный интерфейс connection по PEP 249
# ──────────────────────────────────────────────────────────────────────


class DBAPIConnection(Protocol):
    """Duck-typed DBAPI2 connection (sqlite3.Connection | psycopg2.connection)."""

    def cursor(self) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class DBAPICursor(Protocol):
    """Duck-typed DBAPI2 cursor."""

    def execute(self, sql: str, parameters: Any = ...) -> Any: ...
    def executemany(self, sql: str, seq_of_parameters: Any = ...) -> Any: ...
    def fetchone(self) -> Any: ...
    def fetchall(self) -> list[Any]: ...


# ──────────────────────────────────────────────────────────────────────
# Connector — фабрика и менеджер соединения
# ──────────────────────────────────────────────────────────────────────


class Connector(ABC):
    """Абстрактный коннектор к БД."""

    param_style: str = "qmark"  # "qmark" (?) или "format" (%s)

    @property
    @abstractmethod
    def connection(self) -> DBAPIConnection:
        """Основное (разделяемое) соединение."""
        ...

    @abstractmethod
    def connect(self) -> DBAPIConnection:
        """Новое короткоживущее соединение."""
        ...

    @abstractmethod
    def close(self) -> None: ...

    def adapt_sql(self, sql: str) -> str:
        """Адаптировать SQL под параметрический стиль БД."""
        if self.param_style == "format":
            return sql.replace("?", "%s")
        return sql


# ──────────────────────────────────────────────────────────────────────
# SQLite
# ──────────────────────────────────────────────────────────────────────


class SqliteConnector(Connector):
    """Connector для SQLite (по умолчанию, без DATABASE_URL)."""

    param_style = "qmark"

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        check_same_thread: bool = False,
        pragmas: tuple[str, ...] = ("PRAGMA foreign_keys = ON",),
    ) -> None:
        self.db_path = Path(db_path or os.environ.get("DB_PATH", DEFAULT_DB_PATH))
        self.check_same_thread = check_same_thread
        self.pragmas = pragmas
        self._connection: Any | None = None

    @property
    def connection(self) -> Any:
        import sqlite3

        if self._connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=self.check_same_thread,
            )
            conn.row_factory = sqlite3.Row
            for pragma in self.pragmas:
                conn.execute(pragma)
            self._connection = conn
        return self._connection

    def connect(self) -> Any:
        import sqlite3

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=self.check_same_thread,
        )
        connection.row_factory = sqlite3.Row
        for pragma in self.pragmas:
            connection.execute(pragma)
        return connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


# ──────────────────────────────────────────────────────────────────────
# PostgreSQL
# ──────────────────────────────────────────────────────────────────────


class PostgresConnector(Connector):
    """Connector для PostgreSQL (когда задана DATABASE_URL)."""

    param_style = "format"

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ["DATABASE_URL"]
        self._connection: Any = None  # psycopg2.connection

    @property
    def connection(self) -> Any:
        if self._connection is None:
            import psycopg2
            import psycopg2.extras

            self._connection = psycopg2.connect(self.database_url)
            self._connection.autocommit = False
            # Используем RealDictCursor для row_factory как sqlite3.Row
            self._connection.cursor_factory = psycopg2.extras.RealDictCursor
        return self._connection

    def connect(self) -> Any:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(self.database_url)
        conn.autocommit = False
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


# ──────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────


def create_connector(
    database_url: str | None = None,
    db_path: str | Path | None = None,
) -> Connector:
    """Создать коннектор на основе DATABASE_URL или DB_PATH.

    Приоритет:
      1. Явный database_url
      2. Переменная окружения DATABASE_URL
      3. SQLite (через DB_PATH или дефолт)
    """
    url = database_url or os.environ.get("DATABASE_URL")
    if url:
        logger.info("Using PostgreSQL connector: %s", _mask_password(url))
        return PostgresConnector(url)
    logger.info(
        "Using SQLite connector (path=%s)",
        db_path or os.environ.get("DB_PATH", DEFAULT_DB_PATH),
    )
    return SqliteConnector(db_path)


def _mask_password(url: str) -> str:
    """Скрыть пароль в URL для логов."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    if parsed.password:
        return urlunparse(
            parsed._replace(netloc=f"{parsed.username}:****@{parsed.hostname}")
        )
    return url
