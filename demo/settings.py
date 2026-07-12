"""Bridge to shared settings in helperium_sdk.settings.

Kept for backward compatibility — all code that imports from demo.settings
will transparently use the canonical settings defined in helperium_sdk.
"""

from __future__ import annotations

from pathlib import Path

from helperium_sdk.settings import DemoSettings, project_root
from helperium_sdk.settings import settings as _settings  # noqa: F401 — re-exported below

# Re-export for backward compatibility
PROJECT_ROOT: Path = project_root()
settings = _settings
DemoSettings = DemoSettings  # type: ignore[misc] — re-exported for type-checking
