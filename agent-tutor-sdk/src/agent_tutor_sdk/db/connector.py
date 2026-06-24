"""DB-connector: абстракция над DBAPI2 (SQLite / PostgreSQL).

Позволяет переключать бэкенд через DATABASE_URL:
  - не задана → SQLite (локальная universtity.db)
  - postgresql://... → PostgreSQL (Docker или внешний)
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# SDK lives at agent-tutor-sdk/src/agent_tutor_sdk/db/connector.py
# Project root is 5 levels up: agent-tutor-sdk/src/agent_tutor_sdk/db/connector.py
#   → agent-tutor-sdk/src/agent_tutor_sdk/db/
#   → agent-tutor-sdk/src/agent_tutor_sdk/
#   → agent-tutor-sdk/src/
#   → agent-tutor-sdk/
#   → project root (parent of agent-tutor-sdk/)
_PROJECT_ROOT_CANDIDATE = Path(__file__).resolve().parent.parent.parent.parent.parent
# Fallback: if running from a non-workspace setup (e.g., tests), try env
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", str(_PROJECT_ROOT_CANDIDATE)))
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
# Helpers
# ──────────────────────────────────────────────────────────────────────


def is_operational_error(exc: BaseException) -> bool:
    """Проверить, относится ли исключение к категории operational.

    OperationalError — потеря соединения, таймаут и т.д.
    Используется для автоматического переоткрытия thread-local соединения.
    """
    try:
        import psycopg2

        return isinstance(exc, psycopg2.OperationalError)
    except ImportError:
        return False


# ──────────────────────────────────────────────────────────────────────
# PostgreSQL
# ──────────────────────────────────────────────────────────────────────


class PostgresConnector(Connector):
    """Connector для PostgreSQL (когда задана DATABASE_URL).

    Использует ThreadedConnectionPool для устойчивости:
      - если соединение оборвалось, его можно переоткрыть
      - несколько воркеров могут работать параллельно
      - pool сам отслеживает min/max соединений
    """

    param_style = "format"

    def __init__(
        self,
        database_url: str | None = None,
        *,
        min_conn: int = 1,
        max_conn: int = 10,
    ) -> None:
        self.database_url = database_url or os.environ["DATABASE_URL"]
        self.min_conn = max(1, min_conn)
        self.max_conn = max(self.min_conn, max_conn)
        self._pool: Any | None = None
        self._local = threading.local()

    def _init_pool(self) -> None:
        """Ленивая инициализация пула (создаётся при первом обращении)."""
        if self._pool is not None:
            return
        from psycopg2.pool import ThreadedConnectionPool

        logger.info(
            "Initializing PostgreSQL pool (min=%d, max=%d)",
            self.min_conn,
            self.max_conn,
        )
        # ThreadedConnectionPool поддерживает min/max соединений и блокируется,
        # если свободных нет. Потокобезопасен.
        self._pool = ThreadedConnectionPool(
            self.min_conn, self.max_conn, self.database_url
        )
        # Настраиваем курсор по умолчанию на RealDictCursor
        self._configure_pool_cursors()

    def _configure_pool_cursors(self) -> None:
        """Прокидывает RealDictCursor на все соединения в пуле."""
        import psycopg2.extras

        # Заимствуем и возвращаем каждое соединение, чтобы настроить
        for _ in range(self.min_conn):
            conn = self._pool.getconn()
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            self._pool.putconn(conn)

    @property
    def pool(self) -> Any:
        """Получить пул (ленивая инициализация)."""
        if self._pool is None:
            self._init_pool()
        return self._pool

    def _configure_connection(self, conn: Any) -> None:
        """Настроить autocommit и cursor_factory для нового соединения."""
        import psycopg2.extras

        conn.autocommit = False
        if conn.cursor_factory != psycopg2.extras.RealDictCursor:
            conn.cursor_factory = psycopg2.extras.RealDictCursor

    @property
    def connection(self) -> Any:
        """Соединение для текущего потока (из пула).

        Каждый поток получает своё соединение (thread-local), что
        исключает гонки курсоров и других ресурсов между потоками.
        """
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = self.pool.getconn()
            try:
                self._configure_connection(self._local.conn)
            except Exception:
                # Если настройка сломалась — отдаём соединение обратно
                self.pool.putconn(self._local.conn)
                self._local.conn = None
                raise
        return self._local.conn

    def connect(self) -> Any:
        """Новое соединение из пула (caller обязан вернуть через putconn)."""
        conn = self.pool.getconn()
        self._configure_connection(conn)
        return conn

    def putconn(self, conn: Any) -> None:
        """Вернуть соединение в пул."""
        if self._pool is not None and conn is not None:
            # Если соединение в плохом состоянии — закрываем вместо возврата
            if conn.closed or conn.status != 0:
                try:
                    conn.close()
                except Exception:
                    pass
                self._pool.putconn(conn, close=True)
            else:
                self._pool.putconn(conn)

    def reset_thread_connection(self) -> None:
        """Сбросить thread-local соединение (например, при ошибке).

        Использовать в коде, который перехватывает OperationalError:
            try: ...
            except psycopg2.OperationalError:
                connector.reset_thread_connection()
                raise
        """
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                self.putconn(conn)
            except Exception:
                pass
            self._local.conn = None

    def close(self) -> None:
        """Закрыть все соединения в пуле."""
        if self._local.conn is not None:
            try:
                self.putconn(self._local.conn)
            except Exception:
                pass
            self._local.conn = None
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None


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
