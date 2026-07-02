"""Pytest configuration and shared fixtures.

The test suite is deliberately Qt-free: the fragile widget-level PySide6 tests
were removed, and the UI layer is excluded from the coverage gate (see
.coveragerc). UI-layer logic that is pure Python is tested without a
QApplication under tests/ui_logic.
"""
