"""Tab bar whose keyboard cursor is separate from its selection.

Qt ties a QTabBar's focus to its current tab, so a plainly focused tab bar
can only ever ring the tab the user is already sitting on. That is a dead
stop: an already-current control is not a stop, and landing on it costs a
keypress that changes nothing.

This bar carries its own cursor instead. Entering the strip puts the cursor
on the next tab that is not the current one, Up and Down move it (wrapping,
skipping the current tab and any disabled or hidden one) and Enter or Space
commits the switch. Walking the ring therefore never changes which tab is
shown; only an explicit activation does.

The cursor paints as the same green ring every other stop uses, on the pill
geometry theme_qss gives the tabs. Those metrics are imported rather than
repeated, so the ring cannot drift away from the pill it outlines.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QTabBar

from clear_budget.ui import theme
from clear_budget.ui.theme_qss import (
    TAB_BORDER_PX,
    TAB_MARGIN_BOTTOM_PX,
    TAB_MARGIN_RIGHT_PX,
    TAB_RADIUS_PX,
)
from clear_budget.ui.widgets._tab_cursor import (
    NO_CURSOR,
    next_candidate,
    next_candidate_bounded,
)

__all__ = ["NO_CURSOR", "NavTabBar"]

# The stylesheet border is drawn inside the pill's box, so a centred pen of
# the same width has to sit half a width in to land on the same pixels.
_STROKE_INSET = TAB_BORDER_PX / 2


class NavTabBar(QTabBar):
    """A QTabBar with a keyboard cursor independent of the current tab."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cursor = NO_CURSOR
        self.currentChanged.connect(self._on_current_changed)

    # ---- cursor state -------------------------------------------------------
    def cursor_index(self) -> int:
        """The tab the keyboard cursor is on, or NO_CURSOR when it is off."""
        return self._cursor

    def enter_cursor(self, delta: int) -> None:
        """Put the cursor on the strip's first candidate from the entry END.

        The ring arrives from one side or the other, so it enters at that side:
        arriving forward lands on the LEFTMOST usable tab and walks right,
        arriving backward lands on the RIGHTMOST and walks left. Entering
        beside the current tab instead, as this did, meant a forward pass could
        only ever reach the tabs to its right, and the rest of the strip was
        unreachable without turning round.

        The tab already showing is never a candidate: landing on it costs a
        keypress that changes nothing.
        """
        edge = -1 if delta > 0 else self.count()
        self._set_cursor(
            next_candidate_bounded(
                count=self.count(), start=edge, delta=delta, skip=self._skipped()
            )
        )

    def move_cursor(self, delta: int) -> None:
        """Walk the cursor one candidate on, wrapping at both ends.

        The strip's OWN keys, Up and Down: they stay inside the tab bar, so
        wrapping is right and the cursor can circle the strip indefinitely.
        """
        start = self._cursor if self._cursor != NO_CURSOR else self.currentIndex()
        self._set_cursor(self._next_candidate(start, delta))

    def step_cursor(self, delta: int) -> bool:
        """Walk the cursor one candidate on WITHOUT wrapping; did it move?

        Tab and Shift+Tab, which are the whole window's keys rather than the
        strip's. Every tab is a stop on the ring, so stepping back from Archive
        reaches Solvency rather than jumping out of the strip to the menu bar,
        which is where the ring used to send it. Returning False at the end of
        the strip is what lets the ring carry on out of it: wrapping here would
        trap the ring in the tab bar for ever.
        """
        start = self._cursor if self._cursor != NO_CURSOR else self.currentIndex()
        index = next_candidate_bounded(
            count=self.count(), start=start, delta=delta, skip=self._skipped()
        )
        if index == NO_CURSOR:
            return False
        self._set_cursor(index)
        return True

    def clear_cursor(self) -> None:
        """Take the cursor off the strip entirely."""
        self._set_cursor(NO_CURSOR)

    def commit_cursor(self) -> bool:
        """Switch to the cursor tab; return whether a switch happened."""
        index = self._cursor
        if index == NO_CURSOR:
            return False
        self.setCurrentIndex(index)
        return True

    # ---- candidate walking --------------------------------------------------
    def _skipped(self) -> frozenset[int]:
        """Tabs the cursor may not rest on: the current one, and unusable ones."""
        return frozenset(
            index
            for index in range(self.count())
            if index == self.currentIndex()
            or not self.isTabEnabled(index)
            or not self.isTabVisible(index)
        )

    def _next_candidate(self, start: int, delta: int) -> int:
        """The first candidate from `start` in `delta`'s direction, wrapping."""
        return next_candidate(
            count=self.count(), start=start, delta=delta, skip=self._skipped()
        )

    def _set_cursor(self, index: int) -> None:
        if index != self._cursor:
            self._cursor = index
            self.update()

    def _on_current_changed(self, index: int) -> None:
        # The tab just selected stops being a candidate, whether it was chosen
        # from the keyboard or clicked, so move the cursor off it rather than
        # leave a ring on the tab the selection colour already marks.
        if self._cursor == index:
            self._set_cursor(self._next_candidate(index, 1))

    # ---- painting -----------------------------------------------------------
    def focusOutEvent(self, event) -> None:
        # The cursor is a keyboard affordance and must not outlive the focus.
        self.clear_cursor()
        super().focusOutEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._cursor == NO_CURSOR or not self.hasFocus():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(theme.colours()["ring"]), TAB_BORDER_PX))
        radius = TAB_RADIUS_PX - _STROKE_INSET
        painter.drawRoundedRect(self._pill_rect(self._cursor), radius, radius)
        painter.end()

    def _pill_rect(self, index: int) -> QRectF:
        """The drawn pill inside the tab's slot, as the stylesheet lays it out."""
        rect = QRectF(self.tabRect(index))
        return rect.adjusted(
            _STROKE_INSET,
            _STROKE_INSET,
            -TAB_MARGIN_RIGHT_PX - _STROKE_INSET,
            -TAB_MARGIN_BOTTOM_PX - _STROKE_INSET,
        )
