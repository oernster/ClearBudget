"""Shared fixtures for UI tests.

Auto-patches confirmation dialogs so they do not block headless test
execution: QMessageBox.question returns Yes, and the bill-delete scope
dialog returns "wipe" (full delete). Tests wanting the history-safe
"stop" path override MonthView._ask_delete_scope themselves.
"""

import pytest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from clear_budget.ui.views.month_view import MonthView


@pytest.fixture(autouse=True)
def auto_accept_message_boxes():
    """Auto-confirm blocking dialogs in UI tests."""
    with (
        patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ),
        patch.object(MonthView, "_ask_delete_scope", return_value="wipe"),
    ):
        yield
