"""Application-wide keyboard navigation - the Meridian ring for widgets.

One event filter drives a single explicit focus ring: the menu-bar titles,
then the active tab's stops (each view's nav_targets()). Tab and Right step
forward, Shift+Tab and Backtab and Left step back, both wrapping; the
horizontal arrows are tested first so they step the ring everywhere, out of an
open menu or out of a table. Up and Down stay internal to a stop that owns
them, such as a table walking its rows; Enter and Space activate.

There is no tab-bar case here any more. The four tabs are ordinary buttons in
each view's navigation tray, so each is a stop like any other: walking the
ring moves focus and switches nothing, Enter or Space commits. That used to
need a QTabBar subclass carrying its own cursor, because Qt ties a tab bar's
focus to its CURRENT tab and a focused bar could therefore only ever ring the
tab the user was already on. Inside an open menu the toolkit
keeps two horizontal-arrow cases: Right on a submenu item enters the submenu
and Left inside a submenu exits back to its parent; every other Left/Right
still steps the ring. Inside a modal dialog the same arrows walk the dialog's
own tab order and Enter toggles a focused checkbox. Text inputs always keep
their arrows for the caret.
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
_TABLE = "table"
_WIDGET = "widget"


class KeyboardNavigator(QObject):
    """Single explicit focus ring for the main window plus dialog arrow keys."""

    def __init__(self, *, window, menubar, current_stops, entry_stop=None) -> None:
        """current_stops is a callable returning the active tab's widgets.

        entry_stop, when given, is a callable naming the widget the ring is
        entered AT from a neutral start (launch or a tab switch): a view may
        put the first Tab on the control its tab is opened for rather than on
        the File menu. A None or a widget not currently on the ring falls
        back to the ring's first stop.
        """
        super().__init__(window)
        self._window = window
        self._menubar = menubar
        self._current_stops = current_stops
        self._entry_stop = entry_stop
        QApplication.instance().installEventFilter(self)

    # ---- ring construction --------------------------------------------------
    def _stops(self) -> list:
        stops = [
            (_MENU, action)
            for action in self._menubar.actions()
            if action.isVisible() and action.isEnabled()
        ]
        for widget in self._current_stops():
            if widget is None or not (widget.isEnabled() and widget.isVisible()):
                continue
            kind = _TABLE if isinstance(widget, QTableWidget) else _WIDGET
            stops.append((kind, widget))
        return stops

    def _current_index(self, stops: list) -> int:
        focus = QApplication.focusWidget()
        # A stale activeAction can outlive focus moving elsewhere; the title
        # highlight only counts as the current stop while the bar owns focus
        # or one of its menus is open (walking a menu's items moves focus to
        # the QMenu popup while the title stays the current ring stop).
        menu_owns_keys = self._menubar.hasFocus() or isinstance(
            QApplication.activePopupWidget(), QMenu
        )
        active = self._menubar.activeAction() if menu_owns_keys else None
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

    def _goto(self, stop, delta: int) -> None:
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
            self._goto(self._entry(stops, delta), delta)
            return
        self._goto(stops[(index + delta) % len(stops)], delta)

    def _entry(self, stops: list, delta: int):
        """The stop the ring is entered at from a neutral start.

        Forward entry prefers the active view's declared entry stop when it
        is on the ring; backward entry and every fallback keep the old ends.
        """
        if delta > 0 and self._entry_stop is not None:
            preferred = self._entry_stop()
            for stop in stops:
                kind, target = stop
                if kind != _MENU and target is preferred:
                    return stop
        return stops[0 if delta > 0 else -1]

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
        # A table is one stop: Left/Right step the ring out of it (Up/Down
        # stay native for its rows; a cell editor is a text input and was
        # already given its arrows above).
        if key == Qt.Key.Key_Right:
            modal.focusNextChild()
        else:
            modal.focusPreviousChild()
        return True

    # ---- main-window surface ------------------------------------------------
    def _window_keys(self, event) -> bool:
        key = event.key()
        focus = QApplication.focusWidget()
        popup = QApplication.activePopupWidget()

        if key in _FORWARD_KEYS or key in _BACK_KEYS:
            if key in _ARROW_LR and isinstance(focus, _TEXT_ENTRY_TYPES):
                return False
            if key in _ARROW_LR and self._submenu_arrow(popup, key):
                return False
            self._step(1 if key in _FORWARD_KEYS else -1)
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

    @staticmethod
    def _submenu_arrow(popup, key) -> bool:
        # Qt owns two horizontal-arrow cases inside an open menu: Right on an
        # item that has a submenu enters it (first item active) and Left inside
        # a submenu closes back to the parent item. Yield those to the toolkit;
        # every other Left/Right in a menu still steps the ring.
        if not isinstance(popup, QMenu):
            return False
        if key == Qt.Key.Key_Right:
            action = popup.activeAction()
            return action is not None and action.menu() is not None
        return isinstance(popup.parentWidget(), QMenu)

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
