"""Application-wide keyboard navigation - the Meridian ring for widgets.

One event filter drives a single explicit focus ring: the menu-bar titles,
then the tab bar, then the active tab's stops (each view's nav_targets()).
Tab and Right step forward, Shift+Tab and Backtab and Left step back, both
wrapping, and the horizontal arrows are tested first so they step the ring
everywhere: out of an open menu, out of a table, out of the tab bar. Up and
Down stay internal to a stop that owns them (a table walks its rows, the tab
bar cycles tabs); Enter and Space activate. Inside a modal dialog the same
arrows walk the dialog's own tab order and Enter toggles a focused checkbox.
Text inputs always keep their arrows for the caret.
"""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTextEdit,
)

_FORWARD_KEYS = (Qt.Key.Key_Tab, Qt.Key.Key_Right)
_BACK_KEYS = (Qt.Key.Key_Backtab, Qt.Key.Key_Left)
_ARROW_LR = (Qt.Key.Key_Right, Qt.Key.Key_Left)
_ACTIVATE_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)

# Widgets that keep the horizontal arrows for their caret or value.
_TEXT_ENTRY_TYPES = (
    QLineEdit,
    QAbstractSpinBox,
    QTextEdit,
    QPlainTextEdit,
    QComboBox,
)

_MENU = "menu"
_TABS = "tabs"
_TABLE = "table"
_WIDGET = "widget"


class KeyboardNavigator(QObject):
    """Single explicit focus ring for the main window plus dialog arrow keys."""

    def __init__(self, *, window, menubar, tabbar, current_stops) -> None:
        """current_stops is a callable returning the active tab's widgets."""
        super().__init__(window)
        self._window = window
        self._menubar = menubar
        self._tabbar = tabbar
        self._current_stops = current_stops
        QApplication.instance().installEventFilter(self)

    # ---- ring construction --------------------------------------------------
    def _stops(self) -> list:
        stops = [
            (_MENU, action)
            for action in self._menubar.actions()
            if action.isVisible() and action.isEnabled()
        ]
        stops.append((_TABS, self._tabbar))
        for widget in self._current_stops():
            if widget is None or not (widget.isEnabled() and widget.isVisible()):
                continue
            kind = _TABLE if isinstance(widget, QTableWidget) else _WIDGET
            stops.append((kind, widget))
        return stops

    def _current_index(self, stops: list) -> int:
        focus = QApplication.focusWidget()
        # A stale activeAction can outlive focus moving elsewhere; the title
        # highlight only counts as the current stop while the bar owns focus.
        active = self._menubar.activeAction() if self._menubar.hasFocus() else None
        for i, (kind, target) in enumerate(stops):
            if kind == _MENU:
                if active is target:
                    return i
            elif target is focus:
                return i
        if focus is not None:
            for i, (kind, target) in enumerate(stops):
                if kind != _MENU and target.isAncestorOf(focus):
                    return i
        return -1

    def _goto(self, stop) -> None:
        kind, target = stop
        popup = QApplication.activePopupWidget()
        if popup is not None:
            popup.hide()
        if kind == _MENU:
            self._menubar.setFocus(Qt.FocusReason.TabFocusReason)
            self._menubar.setActiveAction(target)
            return
        # Leaving the bar for a body stop: clear the title highlight, else the
        # bar keeps eating the arrows as native menu navigation.
        self._menubar.setActiveAction(None)
        target.setFocus(Qt.FocusReason.TabFocusReason)

    def _step(self, delta: int) -> None:
        stops = self._stops()
        if not stops:
            return
        index = self._current_index(stops)
        if index < 0:
            self._goto(stops[0 if delta > 0 else -1])
            return
        self._goto(stops[(index + delta) % len(stops)])

    # ---- event filter -------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        modal = QApplication.activeModalWidget()
        if modal is not None:
            return self._dialog_keys(modal, event)
        if not self._window.isActiveWindow():
            return False
        return self._window_keys(event)

    # ---- dialog surface -----------------------------------------------------
    def _dialog_keys(self, modal, event) -> bool:
        key = event.key()
        focus = QApplication.focusWidget()
        if key in _ACTIVATE_KEYS and isinstance(focus, (QCheckBox, QRadioButton)):
            # Enter on a checkbox toggles it rather than firing the default
            # button and submitting the form under the user.
            if focus.isEnabled():
                focus.click()
            return True
        if key not in _ARROW_LR:
            return False
        if isinstance(focus, _TEXT_ENTRY_TYPES):
            return False
        if QApplication.activePopupWidget() is not None:
            return False
        if focus is not None and self._inside_table(focus):
            return False
        if key == Qt.Key.Key_Right:
            modal.focusNextChild()
        else:
            modal.focusPreviousChild()
        return True

    @staticmethod
    def _inside_table(widget) -> bool:
        parent = widget
        while parent is not None:
            if isinstance(parent, QTableWidget):
                return True
            parent = parent.parentWidget()
        return False

    # ---- main-window surface ------------------------------------------------
    def _window_keys(self, event) -> bool:
        key = event.key()
        focus = QApplication.focusWidget()
        popup = QApplication.activePopupWidget()

        if key in _FORWARD_KEYS or key in _BACK_KEYS:
            if key in _ARROW_LR and isinstance(focus, _TEXT_ENTRY_TYPES):
                return False
            self._step(1 if key in _FORWARD_KEYS else -1)
            return True

        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and focus is self._tabbar:
            count = self._tabbar.count()
            delta = 1 if key == Qt.Key.Key_Down else -1
            self._tabbar.setCurrentIndex((self._tabbar.currentIndex() + delta) % count)
            return True

        if (
            key in _ACTIVATE_KEYS
            and isinstance(focus, (QPushButton, QCheckBox))
            and focus.isEnabled()
        ):
            # Outside a dialog, Qt gives Enter no meaning on buttons or
            # checkboxes; make it equal to Space.
            focus.click()
            return True

        if key == Qt.Key.Key_Space:
            return self._space_in_menus(popup)
        return False

    def _space_in_menus(self, popup) -> bool:
        # Qt's Windows styles ignore Space in menus; make it equal to Enter.
        if isinstance(popup, QMenu):
            action = popup.activeAction()
            if action is not None and action.menu() is None:
                popup.close()
                self._menubar.setActiveAction(None)
                action.trigger()
                return True
            return False
        active = self._menubar.activeAction()
        if active is not None and self._menubar.hasFocus():
            menu = active.menu()
            if menu is not None:
                geometry = self._menubar.actionGeometry(active)
                menu.popup(self._menubar.mapToGlobal(geometry.bottomLeft()))
                return True
        return False
