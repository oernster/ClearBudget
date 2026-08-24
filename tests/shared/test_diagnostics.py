"""A failure must leave something behind to read.

The application shipped as a windowed build with no console and no logging
of any kind. Every fault therefore produced one symptom, "nothing happened",
leaving no trace: no traceback, no log file, nothing to diagnose from. These
pin the instrumentation that ends that.
"""

from __future__ import annotations

import logging

from clear_budget.shared import diagnostics


def _read_log(log_dir):
    return (log_dir / diagnostics.LOG_NAME).read_text(encoding="utf-8")


class TestTheLogFile:
    def test_installing_creates_the_log_file(self, tmp_path):
        path = diagnostics.install(tmp_path / "logs", set_hook=lambda hook: None)
        assert path is not None
        assert path.is_file()

    def test_it_creates_the_log_directory_when_absent(self, tmp_path):
        target = tmp_path / "not" / "yet" / "logs"
        assert diagnostics.install(target, set_hook=lambda hook: None) is not None
        assert target.is_dir()

    def test_messages_are_written_and_flushed(self, tmp_path):
        log_dir = tmp_path / "logs"
        diagnostics.install(log_dir, set_hook=lambda hook: None)
        diagnostics.log("opening budget %s", "budget_oliver.db")
        assert "opening budget budget_oliver.db" in _read_log(log_dir)

    def test_a_log_directory_that_cannot_be_made_does_not_stop_the_app(self, tmp_path):
        """No log is bad; no application because there is no log is worse."""
        blocker = tmp_path / "blocker"
        blocker.write_text("I am a file, not a directory", encoding="utf-8")

        assert diagnostics.install(blocker / "logs", set_hook=lambda hook: None) is None

    def test_installing_twice_does_not_double_up_handlers(self, tmp_path):
        log_dir = tmp_path / "logs"
        diagnostics.install(log_dir, set_hook=lambda hook: None)
        diagnostics.install(log_dir, set_hook=lambda hook: None)
        diagnostics.log("once")
        assert _read_log(log_dir).count("once") == 1
        assert len(logging.getLogger(diagnostics.LOGGER_NAME).handlers) == 1


class TestUncaughtExceptionsAreRecorded:
    def test_the_traceback_reaches_the_log(self, tmp_path):
        """PySide6 routes a slot's exception here; stderr goes nowhere."""
        log_dir = tmp_path / "logs"
        captured = []
        diagnostics.install(log_dir, set_hook=captured.append)
        assert captured, "install() did not register an excepthook"

        try:
            raise ValueError("the failure nobody could see")
        except ValueError as exc:
            captured[0](type(exc), exc, exc.__traceback__)

        text = _read_log(log_dir)
        assert "UNCAUGHT EXCEPTION" in text
        assert "the failure nobody could see" in text
        assert "ValueError" in text

    def test_a_database_error_is_named_in_full(self, tmp_path):
        """The exact class of failure that showed the user nothing at all."""
        import sqlite3

        log_dir = tmp_path / "logs"
        captured = []
        diagnostics.install(log_dir, set_hook=captured.append)
        try:
            raise sqlite3.DatabaseError("file is not a database")
        except sqlite3.DatabaseError as exc:
            captured[0](type(exc), exc, exc.__traceback__)

        assert "file is not a database" in _read_log(log_dir)
