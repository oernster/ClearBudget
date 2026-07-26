"""NeutralDialog - a QDialog that opens with nothing focused or highlighted.

A 0x0 focus sink grabs the initial focus on the first show, so no control
lights up until the user presses Tab (or Right) to enter the ring. Once the
sink loses focus it drops out of the tab chain entirely, leaving only real
controls in the cycle. Subclasses overriding showEvent must call super().
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget


class _NeutralStart(QWidget):
    """Invisible 0x0 widget that absorbs a dialog's initial focus once."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(0, 0)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def focusOutEvent(self, event) -> None:  # pragma: no cover - Qt callback
        # Leave the tab chain so the following cycle holds only real controls.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        super().focusOutEvent(event)


class NeutralDialog(QDialog):
    """QDialog with a neutral start: no control focused when it opens."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._neutral_start = _NeutralStart(self)
        self._neutral_started = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._neutral_started:
            self._neutral_started = True
            self._neutral_start.setFocus()
