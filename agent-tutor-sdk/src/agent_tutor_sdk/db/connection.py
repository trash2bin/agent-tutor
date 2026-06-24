"""Backward-compat: всё переехало в agent_tutor_sdk.db.connector."""

from __future__ import annotations

from agent_tutor_sdk.db.connector import (
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
