"""DB layer — backward compat re-export from SDK.

All code should import from `agent_tutor_sdk.db` directly.
This module will be removed after full migration.
"""

from __future__ import annotations

from agent_tutor_sdk.db.connector import (  # noqa: F401
    PROJECT_ROOT,
    DEFAULT_DB_PATH,
    Connector,
    SqliteConnector,
    PostgresConnector,
    create_connector,
    DBAPIConnection,
    DBAPICursor,
)
from agent_tutor_sdk.db.database import Database, get_db, reset_db  # noqa: F401
from agent_tutor_sdk.db.models import (  # noqa: F401
    Student,
    Teacher,
    Group,
    Discipline,
    Grade,
    Lesson,
    ScheduleEntry,
    Document,
    DocumentChunk,
    DocumentImportResult,
    Material,
    RagContext,
    RagSearchResult,
)
