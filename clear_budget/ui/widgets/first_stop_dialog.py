"""FirstStopDialog - a QDialog that opens on its first usable control.

The main window starts neutral: nothing is highlighted until the first Tab,
because the window is a place you look at before you act in it; a menu title
lighting up on launch is noise. A dialog is the opposite. You opened it
deliberately, to do the one thing it is for, so making you press Tab before
anything is focused costs a keystroke and tells you nothing.

So a dialog opens with focus already on its first stop: the first control in
its own tab order that is enabled, visible and takes tab focus. Disabled and
hidden controls are passed over, matching the ring's rule everywhere else
that a dead stop is not a stop. Escape still closes; the ring still wraps
from the last control back to this one.

A reading pane is passed over too. The About credits and the licence text are
scroll areas that come first in their dialogs, so both opened focused on the
page rather than on Close: a dialog opens focused to put somebody where they
can act; a page they can only read is not that place. The pane keeps its
stop, so the keyboard still reaches it. Stellody's dialog skips every scroll
area; this one keeps list and table views, because a table IS something to act
on and the Budgets dialog rightly opens on its table (measured: skipping every
scroll area moved it to a button).

Subclasses overriding showEvent must call super().
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QAbstractScrollArea, QDialog


def is_reading_pane_class(widget_class: type) -> bool:
    """A scroll area that is read rather than acted on: not a list or table."""
    return issubclass(widget_class, QAbstractScrollArea) and not issubclass(
        widget_class, QAbstractItemView
    )


class FirstStopDialog(QDialog):
    """QDialog that focuses its first usable control when it opens."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._first_stop_taken = False

    def first_stop(self):
        """The first enabled, visible, tab-focusable control in this dialog.

        Walks Qt's own focus chain rather than the child list, so the answer
        is the control the user would reach with the first Tab press. Returns
        None for a dialog with nothing focusable in it.
        """
        widget = self.nextInFocusChain()
        seen = set()
        while widget is not None and id(widget) not in seen:
            seen.add(id(widget))
            if self._is_stop(widget):
                return widget
            widget = widget.nextInFocusChain()
        return None

    def _is_stop(self, widget) -> bool:
        return (
            widget is not self
            and self.isAncestorOf(widget)
            and widget.isEnabled()
            and widget.isVisible()
            and not is_reading_pane_class(type(widget))
            and bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._first_stop_taken:
            return
        self._first_stop_taken = True
        stop = self.first_stop()
        if stop is not None:
            stop.setFocus(Qt.FocusReason.TabFocusReason)
