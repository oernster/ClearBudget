"""Keyboard-navigation wiring for MainWindow - extracted for the LOC limit.

Installs the application-wide KeyboardNavigator and gives the main window a
neutral start: a 0x0 focus sink absorbs the initial focus on first show, so
nothing is highlighted and no menu opens until the first Tab or Right enters
the ring. Switching tabs returns to the same neutral start, because hiding
the clicked control makes Qt hand its focus to whatever the new page happens
to offer next.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from clear_budget.ui.keyboard_nav import KeyboardNavigator


class MainWindowNavMixin:
    """Neutral start and keyboard-ring setup for MainWindow."""

    def _setup_keyboard_nav(self, tab_views: list) -> None:
        """Install the navigator over the menu bar and the tab views."""
        self._tab_views = tab_views
        self._focus_sink = QWidget(self)
        self._focus_sink.setFixedSize(0, 0)
        self._focus_sink.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._nav_started = False
        self._navigator = KeyboardNavigator(
            window=self,
            menubar=self.menuBar(),
            current_stops=self._current_nav_stops,
        )
        self.tabs.currentChanged.connect(self._restore_neutral_focus)

    def _restore_neutral_focus(self, _index: int) -> None:
        """Send focus back to the sink whenever the shown tab changes.

        Switching tabs hides the control that was clicked, so Qt hands its
        focus to whatever happens to come next in the newly shown page's
        chain. That painted the green ring on a tray control the user never
        aimed at; beside the accent border on the current tab it read as two
        tabs being current at once.

        The sink is used rather than a chosen control because a new page
        starts neutral for the same reason the window does on launch: nothing
        is highlighted until the first Tab or Right enters the ring. Qt has
        already moved the focus by the time this signal arrives (measured, not
        assumed), so setting it here lands last and nothing overwrites it.
        """
        self._focus_sink.setFocus()

    def _current_nav_stops(self) -> list:
        index = self.tabs.currentIndex()
        if not 0 <= index < len(self._tab_views):
            return []
        view = self._tab_views[index]
        stops = list(view.nav_targets()) if hasattr(view, "nav_targets") else []
        # The page body LAST, after the controls in the tray above it. Without
        # it the ring ran out of stops at the theme toggle and wrapped straight
        # back to the File menu, so a long page (Solvency) could be read only
        # with the mouse: there was no way to put the keyboard on the thing the
        # arrows would have scrolled. It appears only while the page actually
        # overflows, so a short tab still wraps at the toggle.
        page = self.tabs.widget(index)
        scroll = page.nav_scroll_stop() if hasattr(page, "nav_scroll_stop") else None
        if scroll is not None:
            stops.append(scroll)
        return stops

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._nav_started:
            self._nav_started = True
            self._focus_sink.setFocus()
