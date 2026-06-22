"""Backward-compat: всё переехало в db.connector."""

from __future__ import annotations

from db.connector import (
    PROJECT_ROOT,
    DEFAULT_DB_PATH,
    Connector,
    SqliteConnector,
    PostgresConnector,
    create_connector,
    DBAPIConnection,
    DBAPICursor,
)

__all__ = [
    "PROJECT_ROOT",
    "DEFAULT_DB_PATH",
    "Connector",
    "SqliteConnector",
    "PostgresConnector",
    "create_connector",
    "DBAPIConnection",
    "DBAPICursor",
]
