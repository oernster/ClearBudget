"""Keyboard-navigation wiring for MainWindow - extracted for the LOC limit.

Installs the application-wide KeyboardNavigator and gives the main window a
neutral start: a 0x0 focus sink absorbs the initial focus on first show, so
nothing is highlighted and no menu opens until the first Tab or Right enters
the ring.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from clear_budget.ui.keyboard_nav import KeyboardNavigator


class MainWindowNavMixin:
    """Neutral start and keyboard-ring setup for MainWindow."""

    def _setup_keyboard_nav(self, tab_views: list) -> None:
        """Install the navigator over the menu bar, tab bar and tab views."""
        self._tab_views = tab_views
        self._focus_sink = QWidget(self)
        self._focus_sink.setFixedSize(0, 0)
        self._focus_sink.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._nav_started = False
        self._navigator = KeyboardNavigator(
            window=self,
            menubar=self.menuBar(),
            tabbar=self.tabs.tabBar(),
            current_stops=self._current_nav_stops,
        )

    def _current_nav_stops(self) -> list:
        index = self.tabs.currentIndex()
        if not 0 <= index < len(self._tab_views):
            return []
        view = self._tab_views[index]
        return view.nav_targets() if hasattr(view, "nav_targets") else []

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._nav_started:
            self._nav_started = True
            self._focus_sink.setFocus()
