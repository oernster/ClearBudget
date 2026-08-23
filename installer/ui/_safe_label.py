"""QLabel variants for safer text rendering under DPI/font metric edge cases.

Some Windows DPI/text-scaling combinations can lead to 1-2px clipping of glyphs
in a plain `QLabel` (especially bold, large fonts). This wrapper makes the size
hint slightly larger so layouts allocate enough room.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel, QStyle, QStyleOption, QStylePainter


class SafeLabel(QLabel):
    """A QLabel whose size hints include a small safety buffer."""

    def __init__(
        self,
        *args,
        extra_width_px: int = 6,
        extra_height_px: int = 6,
        draw_dx_px: int = 0,
        draw_dy_px: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._extra_width_px = int(extra_width_px)
        self._extra_height_px = int(extra_height_px)
        # Optional draw offset for stubborn 1px glyph clipping cases.
        self._draw_dx_px = int(draw_dx_px)
        self._draw_dy_px = int(draw_dy_px)

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(
            base.width() + self._extra_width_px,
            base.height() + self._extra_height_px,
        )

    def minimumSizeHint(self) -> QSize:
        base = super().minimumSizeHint()
        return QSize(
            base.width() + self._extra_width_px,
            base.height() + self._extra_height_px,
        )

    def line_height(self) -> int:
        """The height of ONE line of this label's text, buffer included.

        Used to pin a label whose text comes and goes. An empty QLabel is
        shorter than a filled one, so a status line that alternates between a
        message and nothing changes the height of everything laid out below
        it. Reading the metric rather than guessing keeps it right across the
        DPI and text-scaling combinations this class exists for.
        """
        from PySide6.QtGui import QFontMetrics

        self.ensurePolished()
        return QFontMetrics(self.font()).height() + self._extra_height_px

    def paintEvent(self, event) -> None:
        # Default QLabel painting can clip large/bold glyphs by 1px on some
        # Windows DPI/text-scaling configurations. When a draw offset is
        # configured, we paint the text slightly shifted to guarantee all pixels
        # remain visible inside the widget rect.
        if self._draw_dx_px == 0 and self._draw_dy_px == 0:
            super().paintEvent(event)
            return

        painter = QStylePainter(self)

        opt = QStyleOption()
        opt.initFrom(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)

        r = self.contentsRect().adjusted(
            self._draw_dx_px,
            self._draw_dy_px,
            self._draw_dx_px,
            self._draw_dy_px,
        )

        flags = int(self.alignment())
        if self.wordWrap():
            flags |= int(Qt.TextWordWrap)

        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.WindowText))
        painter.drawText(r, flags, self.text())
