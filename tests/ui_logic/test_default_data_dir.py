"""Where a saved or loaded budget is offered by default.

Downloads is for files LEAVING the machine: a viewer package, an exported
graph, a backup zip kept elsewhere. A database saved out of the app and
loaded straight back into it never leaves, so it belongs with the data it is
a copy of. This is the difference these pin, because getting it wrong is
silent: the dialog still opens and still works, just somewhere else.
"""

from __future__ import annotations

from clear_budget.shared.config import Config
from clear_budget.ui.ui_paths import default_data_dir, default_downloads_dir


def test_the_default_is_the_apps_own_data_directory() -> None:
    assert default_data_dir() == Config.app_dir()


def test_the_default_follows_a_redirected_data_directory(isolate_app_dir) -> None:
    """It must honour the redirect; a test would otherwise hit the real one."""
    assert default_data_dir() == isolate_app_dir


def test_it_is_not_the_downloads_folder(isolate_app_dir) -> None:
    """The whole point of the change; asserted so it cannot drift back."""
    assert default_data_dir() != default_downloads_dir()
