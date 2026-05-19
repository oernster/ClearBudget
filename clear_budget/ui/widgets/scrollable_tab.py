"""ScrollableTab — QScrollArea wrapper with visible up/down scroll indicators."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame, QPushButton, QApplication, QStyle
from PySide6.QtCore import Qt
from clear_budget.ui import ui_scale

_INDICATOR_SIZE = 32
_INDICATOR_MARGIN = 10
_SCROLL_STEP = 120

_INDICATOR_STYLE = (
    "QPushButton {"
    "  background-color: rgba(56, 189, 248, 200);"
    "  color: white;"
    "  border: none;"
    "  border-radius: 14px;"
    "  font-size: 20px;"
    "  font-weight: bold;"
    "}"
    "QPushButton:hover {"
    "  background-color: rgba(56, 189, 248, 255);"
    "  border: 2px solid white;"
    "}"
)


class ScrollableTab(QWidget):
    """Wraps a content widget in a QScrollArea and overlays ▲/▼ indicators."""

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidget(content)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(self._scroll)

        sz = ui_scale.px(_INDICATOR_SIZE)
        _style = QApplication.style()
        self._up_btn = QPushButton(self)
        self._up_btn.setIcon(_style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self._up_btn.setFixedSize(sz, sz)
        self._up_btn.setStyleSheet(_INDICATOR_STYLE)
        self._up_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._up_btn.hide()

        self._down_btn = QPushButton(self)
        self._down_btn.setIcon(_style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self._down_btn.setFixedSize(sz, sz)
        self._down_btn.setStyleSheet(_INDICATOR_STYLE)
        self._down_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._down_btn.hide()

        vbar = self._scroll.verticalScrollBar()
        vbar.valueChanged.connect(self._refresh)
        vbar.rangeChanged.connect(self._refresh)

        self._up_btn.clicked.connect(
            lambda: vbar.setValue(vbar.value() - ui_scale.px(_SCROLL_STEP))
        )
        self._down_btn.clicked.connect(
            lambda: vbar.setValue(vbar.value() + ui_scale.px(_SCROLL_STEP))
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition()
        self._refresh()

    def _reposition(self) -> None:
        sz = self._down_btn.width()
        margin = ui_scale.px(_INDICATOR_MARGIN)
        # Leave room for the vertical scrollbar (~16px)
        x = self.width() - sz - margin - ui_scale.px(16)
        self._up_btn.move(x, margin)
        self._down_btn.move(x, self.height() - sz - margin)
        self._up_btn.raise_()
        self._down_btn.raise_()

    def _refresh(self, *_) -> None:
        vbar = self._scroll.verticalScrollBar()
        has_range = vbar.maximum() > vbar.minimum()
        self._up_btn.setVisible(has_range and vbar.value() > vbar.minimum())
        self._down_btn.setVisible(has_range and vbar.value() < vbar.maximum())

    def scroll_area(self) -> QScrollArea:
        return self._scroll
