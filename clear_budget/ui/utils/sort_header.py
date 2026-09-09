"""The header that says which column a table is ordered by, in a real arrow.

Qt's own sort indicator is drawn by the platform style: a few pixels wide;
on Windows it sits along the TOP EDGE of the section rather than beside the
word it qualifies. It answers the question so quietly that a table which had
been reordering itself on a click for months read as one that ignored clicks.

So the indicator is painted here instead, to a size that can be seen from
across the desk and immediately to the RIGHT OF THE HEADING TEXT, where it
reads as belonging to that heading rather than as decoration on the row of
headings. It is a filled triangle for the same reason the spin-box arrows are
images rather than CSS shapes (see `ui/spin_arrows.py`): a shape Qt draws is a
shape that is actually there.

The section carrying the arrow reserves room for it, so the arrow can never
land on the words. Only that one section pays for it, since only one column is
ever sorted.
"""

from __future__ import annotations

from math import ceil

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QHeaderView, QStyle, QStyleOptionHeader

from clear_budget.ui import theme, ui_scale
from clear_budget.ui.utils.table_sort import UNSORTED, SortState

# The arrow is as tall as the heading's own CAPITALS and sits on the same two
# lines they do: its top on the cap height, its base on the baseline. That is
# measured from the font rather than written as a pixel number, so it holds at
# every display scale and follows the heading if the font ever changes. A
# number of its own would agree with the text at exactly one size.
_ARROW_WIDTH_RATIO = 1.5
# Space between the last letter of the heading and the arrow.
_ARROW_GAP_PX = 7


class SortHeaderView(QHeaderView):
    """A horizontal header drawing its own sort arrow beside the heading."""

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setSectionsClickable(True)
        # Qt's own indicator stays off: this class draws the one the user sees
        # and two arrows saying the same thing in two places is one too many.
        self.setSortIndicatorShown(False)
        self._sort: SortState = UNSORTED

    def show_sort(self, state: SortState) -> None:
        """Point the arrow at the column `state` names; hide it while unsorted."""
        self._sort = state
        self.updateGeometries()
        self.viewport().update()

    def _arrow_size(self) -> tuple[float, float]:
        """The arrow's width and height, both taken from the heading font."""
        height = float(self.fontMetrics().capHeight())
        return height * _ARROW_WIDTH_RATIO, height

    def _arrow_span(self) -> int:
        """The width one arrow needs, gap included."""
        width, _height = self._arrow_size()
        return ceil(width) + ui_scale.px(_ARROW_GAP_PX)

    def sectionSizeFromContents(self, logical_index: int) -> QSize:
        """Reserve one arrow's span in the section that carries it.

        ONE span, not two, because this class lays the heading out itself: the
        text and the arrow are centred as a single block, so the width the
        arrow needs is the width the section grows by. Reserving two, which is
        what a centred heading painted by the style would have needed, put
        about sixty points into whichever column was sorted and that was
        enough to push a full Bills table into a horizontal scrollbar.
        """
        size = super().sectionSizeFromContents(logical_index)
        if logical_index != self._sort.column:
            return size
        return QSize(size.width() + self._arrow_span(), size.height())

    def paintSection(self, painter: QPainter, rect, logical_index: int) -> None:
        """Draw the section, with the heading and its arrow as one block."""
        if logical_index != self._sort.column or not rect.isValid():
            super().paintSection(painter, rect, logical_index)
            return
        option = QStyleOptionHeader()
        self.initStyleOptionForIndex(option, logical_index)
        option.rect = rect
        label = str(option.text or "")
        # The chrome is drawn by the style, so the section keeps the
        # background, the border and the hover state the stylesheet gives
        # every other section. Only the LABEL is taken over, so the arrow can
        # be laid out beside it rather than paid for on both sides of a word
        # the style would centre.
        option.text = ""
        self.style().drawControl(QStyle.ControlElement.CE_Header, option, painter, self)
        self._paint_label_and_arrow(painter, rect, label)

    def _paint_label_and_arrow(self, painter, rect, label: str) -> None:
        """The heading and the arrow, centred together in `rect`."""
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(label)
        arrow_width, arrow_height = self._arrow_size()
        gap = ui_scale.px(_ARROW_GAP_PX)
        left = rect.left() + (rect.width() - (text_width + gap + arrow_width)) / 2
        # The style centres the text's LINE BOX in the section, so the baseline
        # is that box's top plus the ascent and the capitals stand one cap
        # height above it. Both the heading and the arrow are drawn to it.
        centre = rect.top() + rect.height() / 2
        baseline = centre - metrics.height() / 2 + metrics.ascent()
        painter.save()
        painter.setPen(QColor(theme.colours()["text_muted"]))
        painter.setFont(self.font())
        painter.drawText(QPointF(left, baseline), label)
        painter.restore()
        self._draw_arrow(
            painter,
            left=left + text_width + gap,
            top=baseline - arrow_height,
            width=arrow_width,
            height=arrow_height,
        )

    def _draw_arrow(self, painter, *, left, top, width, height) -> None:
        """One filled triangle: up while ascending, down while descending."""
        # The heading text is muted on purpose; the arrow takes the full text
        # colour, since it is the one thing on the row that has to be noticed.
        colour = QColor(theme.colours()["text"])
        points = (
            [
                (left, top + height),
                (left + width, top + height),
                (left + width / 2, top),
            ]
            if self._sort.ascending
            else [(left, top), (left + width, top), (left + width / 2, top + height)]
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
        painter.restore()


def install_sort_header(table) -> SortHeaderView:
    """Give `table` a header that draws the sort arrow; return that header.

    Called before the section resize mode is set, since replacing a header
    replaces whatever was configured on the old one.
    """
    header = SortHeaderView(table)
    table.setHorizontalHeader(header)
    return header
