"""Application identity and version.

Keep app identity in one place so the runtime UI, About dialog, logging, and
packaging metadata stay consistent.
"""

from pathlib import Path

APP_NAME: str = "ClearBudget"
APP_AUTHOR: str = "Oliver Ernster"
APP_COPYRIGHT: str = "© 2026 Oliver Ernster"

# Windows taskbar grouping / pinned icon identity.
#
# This should be stable over time; changing it can cause Windows to treat newer
# builds as a different app (separate taskbar grouping / pinned item).
APP_APPUSERMODELID: str = "com.oliverernster.clearbudget"

# Read version from VERSION file in project root
_VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"
__version__: str = (
    _VERSION_FILE.read_text(encoding="utf-8").strip()
    if _VERSION_FILE.exists()
    else "0.0.0-dev"
)
