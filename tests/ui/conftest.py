"""Shared fixtures for UI tests.

Auto-patches QMessageBox.question to return StandardButton.Yes so that
confirmation dialogs (delete bill, delete income, etc.) do not block
headless test execution.
"""

import pytest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox


@pytest.fixture(autouse=True)
def auto_accept_message_boxes():
    """Patch QMessageBox.question to always return Yes in UI tests."""
    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        yield
