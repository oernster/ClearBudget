"""A record of what the application did, plus anything that killed it.

A packaged ClearBudget is a windowed build: it has no console, so anything
written to stderr goes nowhere at all. Until this module existed the
application had no logging of any kind, so a failure produced exactly one
symptom, "nothing happened", leaving nothing behind to read. Three hours
were once spent guessing at a fault that would have named itself in a log
file on the first attempt.

Two things are installed:

  * a file log in the data directory's `logs/`, so the sequence of a session
    (start, sign-in, which budget opened, shutdown) is on disk afterwards;
  * a handler for exceptions nobody caught. PySide6 routes an exception
    raised inside a slot through `sys.excepthook`, which by default prints to
    the stderr a windowed build does not have. Anything reaching it is
    therefore recorded rather than lost.

Installing must never be the reason the application fails to start, so a
logging directory that cannot be created is swallowed and the app runs on
without a log.

British spelling is used in comments.
"""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path
from typing import Callable

LOG_NAME = "clearbudget.log"
LOGGER_NAME = "clearbudget"

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def _build_handler(log_dir: Path) -> logging.Handler:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_dir / LOG_NAME, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMAT))
    return handler


def install(
    log_dir: Path,
    *,
    set_hook: Callable[[Callable], None] | None = None,
) -> Path | None:
    """Start logging to ``log_dir`` and record uncaught exceptions.

    Returns the log file's path; None when logging could not be set up.
    A failure here is never allowed to stop the application starting: no log
    is worse than no application.

    ``set_hook`` is injectable so a test can capture the installed handler
    without replacing the interpreter's own for every later test.
    """
    logger = logging.getLogger(LOGGER_NAME)
    try:
        handler = _build_handler(log_dir)
    except OSError:
        return None

    logger.setLevel(logging.INFO)
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
        existing.close()
    logger.addHandler(handler)
    logger.propagate = False

    setter = set_hook if set_hook is not None else _set_system_hook
    setter(_make_excepthook(logger))
    return log_dir / LOG_NAME


def _set_system_hook(hook: Callable) -> None:  # pragma: no cover - global state
    sys.excepthook = hook


def _make_excepthook(logger: logging.Logger) -> Callable:
    """An excepthook that writes the traceback where it can be read later."""

    def handle(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error("UNCAUGHT EXCEPTION\n%s", text)
        for handler in logger.handlers:
            handler.flush()

    return handle


def log(message: str, *args) -> None:
    """Record one line about what the session is doing."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.info(message, *args)
    for handler in logger.handlers:
        handler.flush()
