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
        centre_on_ink: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._extra_width_px = int(extra_width_px)
        self._extra_height_px = int(extra_height_px)
        # Optional draw offset for stubborn 1px glyph clipping cases.
        self._draw_dx_px = int(draw_dx_px)
        self._draw_dy_px = int(draw_dy_px)
        self._centre_on_ink = bool(centre_on_ink)

    def ink_offset_px(self) -> int:
        """How far to shift the text so its INK centres in the widget.

        Qt centres the LINE BOX, which is not what the eye judges. A line box
        runs from the ascent to the descent; a font's ascent reaches well
        above the height of any capital, so the visible ink of a word sits
        BELOW the centre of the box holding it. On a small label nobody
        notices. On this header's 38px title it measured 8px, enough to make
        the title read as sitting low beside a 14px version string and two
        buttons that have no such gap.

        Qt has no baseline alignment to reach for, so the offset is measured
        instead: the tight bounding rect of THIS text in THIS font, against
        the line box Qt actually centred. Measured rather than tabulated, so
        it follows the DPI, the text-scaling setting and the text itself
        rather than being a pixel someone once read off a screenshot.
        """
        from PySide6.QtGui import QFontMetrics

        self.ensurePolished()
        metrics = QFontMetrics(self.font())
        # tightBoundingRect, never boundingRect. The plain one reports a box
        # that starts at -ascent, so it hands back the LINE BOX under another
        # name and every offset derived from it comes out as exactly zero.
        # Measured that way first, which is how it was caught.
        ink = metrics.tightBoundingRect(self.text())
        if ink.isEmpty():
            return 0
        ink_centre = (ink.top() + ink.bottom()) / 2
        line_centre = (metrics.descent() - metrics.ascent()) / 2
        return round(line_centre - ink_centre)

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

    def metric_minimum_size(self) -> QSize:
        """The smallest box this label's CURRENT text needs, buffer included.

        Derived from FONT METRICS, never from `sizeHint()`; that is the
        whole point of it. `sizeHint()` here is contaminated: Qt derives a
        plain label's hint from its minimum size hint, this class adds its
        safety buffer on top; the caller then writes the result back as
        the new minimum. Feed that cycle once per theme change and the buffer
        is added again every time. Measured: the header title's hint walked
        484 to 634 to 784 to 934 across four theme toggles, exactly +150 and
        +18 a step, which are this label's own two buffers; the window was
        dragged wider with it until it left the screen.

        Nothing here reads a value this class previously wrote, so calling it
        any number of times gives the same answer.
        """
        from PySide6.QtGui import QFontMetrics

        self.ensurePolished()
        metrics = QFontMetrics(self.font())
        tight = metrics.tightBoundingRect(self.text())
        margins = self.contentsMargins()
        return QSize(
            tight.width() + margins.left() + margins.right() + self._extra_width_px,
            metrics.height() + margins.top() + margins.bottom() + self._extra_height_px,
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
        dy = self._draw_dy_px + (self.ink_offset_px() if self._centre_on_ink else 0)
        if self._draw_dx_px == 0 and dy == 0:
            super().paintEvent(event)
            return

        painter = QStylePainter(self)

        opt = QStyleOption()
        opt.initFrom(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)

        r = self.contentsRect().adjusted(
            self._draw_dx_px,
            dy,
            self._draw_dx_px,
            dy,
        )

        flags = int(self.alignment())
        if self.wordWrap():
            flags |= int(Qt.TextWordWrap)

        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.WindowText))
        painter.drawText(r, flags, self.text())
