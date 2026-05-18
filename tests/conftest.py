"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def qapplication():
    """Provide QApplication for UI tests."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
