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

Subclasses overriding showEvent must call super().
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog


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
