"""ThemedComboBox - a combo box that paints its own drop-down arrow.

The platform's arrow and a rounded right-hand corner cannot be had together.
Qt draws `::drop-down` as a native button over the right end of the field.
That button is square, so it paints across the corner the field's own
border-radius rounds: measured side by side, a plain line edit came out
rounded on both sides while the combo beside it was rounded on the left and
square on the right.

Stopping that is one line of stylesheet, `background: transparent` on the
subcontrol; the same line stops the platform drawing the chevron inside it.
Every other route was measured and rejected. `border: none` removes the arrow
too. A replacement built from CSS borders renders as a blank block, because Qt
paints `::down-arrow` as an image. And `width` alone, the only property that
leaves the native arrow intact, moves it without rounding anything.

So the arrow is painted here instead. That also puts its position and its
colour under this module's control rather than the platform's, which is what
lets it stand in from the border by the same distance the text stands in from
the other side while following the active theme rather than guessing at it.

Every combo box in the application is one of these. A plain QComboBox would
now draw no arrow at all, since the stylesheet that rounds the corner is
applied app-wide.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QComboBox

from clear_budget.ui import ui_scale

# How far the chevron's right edge stands in from the field's right border.
# The same inset the fields give their text on the left, so the two ends of
# the control are balanced.
_ARROW_RIGHT_INSET_PT = 8
# The chevron itself: how wide it spans and how far it drops in the middle.
_ARROW_WIDTH_PT = 9
_ARROW_DEPTH_PT = 4
_ARROW_STROKE_PT = 2


class ThemedComboBox(QComboBox):
    """A combo box whose arrow is drawn here, in the active theme's colour."""

    def paintEvent(self, event) -> None:
        """Let the stylesheet draw the field, then add the arrow on top."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._arrow_colour())
        pen.setWidthF(ui_scale.px(_ARROW_STROKE_PT))
        pen.setCapStyle(pen.capStyle().RoundCap)
        pen.setJoinStyle(pen.joinStyle().RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(self._chevron())
        painter.end()

    def _arrow_colour(self) -> QColor:
        """The active theme's text colour, dimmed when the control is off.

        Resolved at PAINT time rather than at build time, because a combo box
        that was already on screen when the theme changed has to repaint in
        the new one; a colour captured in the constructor would not.
        """
        from PySide6.QtWidgets import QApplication

        from clear_budget.ui import theme
        from clear_budget.ui.theme_tokens import tokens_for

        tokens = tokens_for(theme.current_theme(QApplication.instance()))
        return QColor(tokens["text" if self.isEnabled() else "text_disabled"])

    def _chevron(self) -> QPolygonF:
        """The three points of the arrow, measured in from the right border."""
        width = ui_scale.px(_ARROW_WIDTH_PT)
        depth = ui_scale.px(_ARROW_DEPTH_PT)
        right = self.width() - ui_scale.px(_ARROW_RIGHT_INSET_PT)
        left = right - width
        middle = self.height() / 2
        top = middle - depth / 2
        return QPolygonF(
            [
                QPointF(left, top),
                QPointF(left + width / 2, top + depth),
                QPointF(right, top),
            ]
        )
