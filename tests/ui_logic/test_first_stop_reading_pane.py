"""Qt-free tests for which scroll areas a dialog must not open on.

A dialog opens on its first control. The About credits and the licence text are
scroll areas that come first in their dialogs, so they were chosen and the
dialog opened on the page instead of on Close. Lists and tables are also scroll
areas yet are things to act on: the Budgets dialog opens on its table and must
keep doing so. The predicate works on classes, so no QApplication is needed.
"""

from PySide6.QtWidgets import (
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTextBrowser,
    QTextEdit,
    QTreeView,
)

from clear_budget.ui.widgets.first_stop_dialog import is_reading_pane_class


def test_text_and_page_scroll_areas_are_reading_panes():
    for widget_class in (QTextBrowser, QTextEdit, QPlainTextEdit, QScrollArea):
        assert is_reading_pane_class(widget_class), widget_class.__name__


def test_lists_and_tables_stay_openable():
    for widget_class in (QTableWidget, QListWidget, QTreeView):
        assert not is_reading_pane_class(widget_class), widget_class.__name__


def test_a_control_is_not_a_pane():
    assert not is_reading_pane_class(QPushButton)
