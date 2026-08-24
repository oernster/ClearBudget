"""Application identity and version.

Keep app identity in one place so the runtime UI, About dialog, logging and
packaging metadata stay consistent.
"""

from pathlib import Path

APP_NAME: str = "ClearBudget"

# Previous APP_NAME, used to migrate per-user installer data (preferences,
# cache) created by older installs that used the old display name.
#
# The spaced spelling was tried and reverted. It bought nothing and cost a
# great deal: it renamed the install directory out from under every shortcut
# and Start pin already aiming at the old one, so a relaunch met the shell's
# "can't open this item" dialog instead of the app. The
# name is ONE word from here on. This constant points back at the spaced
# spelling only so an install that took it carries its settings forward.
LEGACY_APP_NAME: str = "Clear Budget"
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
