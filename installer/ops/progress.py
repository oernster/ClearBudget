"""Progress reporting for the long-running installer operations.

Install, repair and uninstall each replace or remove a whole bundle, so all
three report a phase and a percentage rather than freezing behind a single
status line. The phases that take the longest (extracting the payload, walking
the repair manifest) are given a span of their own to report within rather than
a single milestone, so the bar moves while the work is happening.

The callback is optional throughout: the operations are callable headlessly
with no reporter attached. British spelling is used in comments.
"""

from __future__ import annotations

from collections.abc import Callable

# The UI accepts either a bare message or a mapping carrying a percentage. Every
# operation now reports the mapping, so the bar never sits at zero and then
# jumps to complete.
ProgressPayload = dict[str, object] | str
ProgressCallback = Callable[[ProgressPayload], None]

PCT_KEY = "pct"
MESSAGE_KEY = "message"

MINIMUM_PCT = 0
COMPLETE_PCT = 100

# --- install, upgrade and reinstall phases -----------------------------------

EXTRACT_START_PCT = 5
EXTRACT_END_PCT = 45
EXTRACT_MESSAGE = "Extracting payload..."
SWAP_PCT = 55
SWAP_MESSAGE = "Installing application files..."
ICON_ASSETS_PCT = 65
ICON_ASSETS_MESSAGE = "Deploying icon assets..."
REGISTER_PCT = 75
REGISTER_MESSAGE = "Registering uninstall entry..."
SHORTCUTS_PCT = 90
SHORTCUTS_MESSAGE = "Creating shortcuts..."
UPDATE_SHORTCUTS_MESSAGE = "Updating shortcuts..."
CLEANUP_PCT = 95
CLEANUP_MESSAGE = "Cleaning up..."

# --- repair phases -----------------------------------------------------------

VERIFY_START_PCT = 5
VERIFY_END_PCT = 70
VERIFY_MESSAGE_TEMPLATE = "Verifying {path}..."
RESTORE_MESSAGE_TEMPLATE = "Restoring {path}..."
RESTORE_SHORTCUTS_PCT = 80
RESTORE_SHORTCUTS_MESSAGE = "Restoring shortcuts..."
RESTORE_REGISTRY_PCT = 90
RESTORE_REGISTRY_MESSAGE = "Restoring registry metadata..."
REPAIR_CLEANUP_PCT = 95
REPAIR_CLEANUP_MESSAGE = "Cleaning up legacy install..."

# --- uninstall phases --------------------------------------------------------

READ_METADATA_PCT = 10
READ_METADATA_MESSAGE = "Reading installation metadata..."
REMOVE_SHORTCUTS_PCT = 30
REMOVE_SHORTCUTS_MESSAGE = "Removing shortcuts..."
REMOVE_REGISTRY_PCT = 55
REMOVE_REGISTRY_MESSAGE = "Removing registry entries..."
REMOVE_FILES_PCT = 80
REMOVE_FILES_MESSAGE = "Removing application files..."

DONE_MESSAGE = "Completed"
UNINSTALL_DONE_MESSAGE = "Uninstall scheduled. Closing..."


def report(callback: ProgressCallback | None, pct: int, message: str) -> None:
    """Send one progress update, doing nothing when no reporter is attached."""
    if callback is None:
        return
    callback({PCT_KEY: int(pct), MESSAGE_KEY: message})


def scaled(done: int, total: int, start: int, end: int) -> int:
    """Return the percentage for ``done`` of ``total`` within a phase's span.

    A total of zero reports the end of the phase: there is nothing to wait for,
    so the phase is already complete.
    """
    if total <= 0:
        return end
    return start + ((end - start) * done) // total
