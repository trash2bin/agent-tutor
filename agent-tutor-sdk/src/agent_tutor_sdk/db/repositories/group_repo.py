"""Репозиторий групп."""

from __future__ import annotations

from agent_tutor_sdk.db.models import Group
from agent_tutor_sdk.db.repositories.base import BaseRepository


class GroupRepo(BaseRepository):
    """Репозиторий для работы с группами."""

    def get_group(self, group_id: str) -> Group | None:
        """Получить группу по ID."""
        row = self.fetch_one("SELECT * FROM groups WHERE id = ?", (group_id,))
        if not row:
            return None
        return Group(
            id=row["id"],
            name=row["name"],
            speciality=row["speciality"],
        )
