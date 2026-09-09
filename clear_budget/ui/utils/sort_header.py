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
from PySide6.QtWidgets import QHeaderView

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
        """Reserve room for the arrow in the section that carries it.

        Twice the arrow's span, because the heading is CENTRED in the section:
        half the reserved width falls on each side of it, so the arrow gets a
        whole span to sit in and the text keeps its own room.
        """
        size = super().sectionSizeFromContents(logical_index)
        if logical_index != self._sort.column:
            return size
        return QSize(size.width() + 2 * self._arrow_span(), size.height())

    def paintSection(self, painter: QPainter, rect, logical_index: int) -> None:
        """Draw the section as usual, then the arrow after its text."""
        super().paintSection(painter, rect, logical_index)
        if logical_index != self._sort.column or not rect.isValid():
            return
        label = self.model().headerData(
            logical_index, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
        )
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(str(label or ""))
        width, height = self._arrow_size()
        left = rect.center().x() + text_width / 2 + ui_scale.px(_ARROW_GAP_PX)
        # The style centres the text's LINE BOX in the section, so the baseline
        # is that box's top plus the ascent and the capitals stand one cap
        # height above it. The arrow is drawn between those same two lines.
        baseline = rect.center().y() - metrics.height() / 2 + metrics.ascent()
        self._draw_arrow(
            painter, left=left, top=baseline - height, width=width, height=height
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
