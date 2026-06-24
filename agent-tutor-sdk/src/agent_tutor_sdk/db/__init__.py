"""DB layer — абстракция над SQLite / PostgreSQL."""

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
from agent_tutor_sdk.db.database import Database, get_db, reset_db
from agent_tutor_sdk.db.models import (
    Student,
    Teacher,
    Group,
    Discipline,
    Grade,
    Lesson,
    ScheduleEntry,
)
from agent_tutor_sdk.db.models import (  # RAG models re-exported for convenience
    Document,
    DocumentChunk,
    DocumentImportResult,
    Material,
    RagContext,
    RagSearchResult,
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
    "Database",
    "get_db",
    "reset_db",
    "Student",
    "Teacher",
    "Group",
    "Discipline",
    "Grade",
    "Lesson",
    "ScheduleEntry",
    "Document",
    "DocumentChunk",
    "DocumentImportResult",
    "Material",
    "RagContext",
    "RagSearchResult",
]
