"""Clickable label widget that emits signal on mouse press."""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Signal
from PySide6.QtGui import QMouseEvent


class ClickableLabel(QLabel):
    """QLabel that emits clicked signal on mouse press."""
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit clicked signal on mouse press."""
        self.clicked.emit()
        super().mousePressEvent(event)
