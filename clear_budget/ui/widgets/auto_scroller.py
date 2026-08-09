"""Gentle auto-scroll for long content.

The cycle holds still for a moment when the surface opens, reads down
slowly, holds at the bottom so the tail can be read, rewinds to the top
at a faster pace, holds briefly and starts over. Manual scrolling (wheel,
click, dragging the scrollbar or the arrow keys) only suspends the cycle:
once the reader has been still for a moment it picks up from wherever
they left it, so taking over by hand never switches the feature off for
the rest of the surface's life. Focus entering the surface (keyboard
navigation into it) suspends it the same way, so the cycle never fights
the reader.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from clear_budget.ui import ui_scale


class AutoScroller(QObject):
    """Cycles a scrollable widget: down slowly, pause, rewind fast, repeat.

    Works on any scroll surface exposing verticalScrollBar() and viewport()
    (a QTextBrowser showing credits or help text, a QScrollArea of cards).
    The widget becomes the scroller's Qt parent, so their lifetimes match.
    The constants are the application's single reading pace: no surface
    gets its own.
    """

    _TICK_MS = 40
    _DOWN_STEP_PX = 1
    # The descent advances one step every second tick: the app's standard
    # reading pace, gentle enough for dense content on every surface.
    _DOWN_TICKS_PER_STEP = 2
    # The rewind is a reposition, not a reading pass, so it travels fast.
    _UP_STEP_PX = 15
    # Hold at the end long enough to finish reading the tail before the
    # rewind takes it away.
    _BOTTOM_PAUSE_MS = 5000
    _TOP_PAUSE_MS = 2000
    # A fresh surface holds still before its first descent, so the reader
    # orients before anything starts to move.
    _START_PAUSE_MS = 5000
    # Stillness required after a manual scroll before the cycle resumes.
    _RESUME_AFTER_MS = 2500

    _DOWN = "down"
    _UP = "up"
    _PAUSE_TOP = "pause_top"
    _PAUSE_BOTTOM = "pause_bottom"
    _MANUAL = "manual"
    _WAITING = (_PAUSE_TOP, _PAUSE_BOTTOM, _MANUAL)
    _MANUAL_EVENTS = (
        QEvent.Type.Wheel,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.KeyPress,
    )

    def __init__(self, area) -> None:
        super().__init__(area)
        self._area = area
        self._bar = area.verticalScrollBar()
        self._down_countdown = self._DOWN_TICKS_PER_STEP
        # Open holding still, then the first descent begins; the guard in
        # the tick means the wait only counts down once content overflows.
        self._phase = self._PAUSE_TOP
        self._wait_ms = self._START_PAUSE_MS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._TICK_MS)
        # The viewport sees the wheel and clicks, the widget sees the keys.
        area.installEventFilter(self)
        area.viewport().installEventFilter(self)
        self._bar.sliderPressed.connect(self.suspend)
        self._bar.sliderReleased.connect(self.suspend)
        self._bar.sliderMoved.connect(self._on_slider_moved)
        # Keyboard navigation into a child is reading by hand too; the child
        # never sees this filter, so watch the application's focus instead.
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    def suspend(self) -> None:
        """Hand the content to the reader and start counting down to resume."""
        self._phase = self._MANUAL
        self._wait_ms = self._RESUME_AFTER_MS

    def _on_slider_moved(self, _value: int) -> None:
        """Dragging the scrollbar counts as reading by hand."""
        self.suspend()

    def _on_focus_changed(self, _old, new) -> None:
        if self._phase == self._PAUSE_TOP and self._wait_ms >= self._START_PAUSE_MS:
            # The dialog placing its OPENING focus on the surface is the
            # dialog acting, not the reader: the untouched start hold already
            # covers it; letting it suspend would swap the 5s orientation
            # hold for the shorter manual wait on every open.
            return
        if isinstance(new, QWidget) and (
            new is self._area or self._area.isAncestorOf(new)
        ):
            self.suspend()

    def eventFilter(self, obj, event) -> bool:
        if event.type() in self._MANUAL_EVENTS:
            self.suspend()
        return False

    def _frozen_under_modal(self) -> bool:
        """Whether a modal above this surface should freeze the cycle.

        Two surfaces reading at once compete for the eye, so while a modal
        dialog is up only ITS surfaces read; anything beneath freezes in
        place (no wait is consumed) and resumes exactly where it was when
        the modal closes.
        """
        modal = QApplication.activeModalWidget()
        if modal is None:
            return False
        return not (modal is self._area.window() or modal.isAncestorOf(self._area))

    def _tick(self) -> None:
        if self._frozen_under_modal():
            return
        maximum = self._bar.maximum()
        if maximum <= 0:
            return
        if self._phase in self._WAITING:
            self._wait_ms -= self._TICK_MS
            if self._wait_ms <= 0:
                self._phase = self._resumed_phase(maximum)
            return
        if self._phase == self._DOWN:
            self._down_countdown -= 1
            if self._down_countdown > 0:
                return
            self._down_countdown = self._DOWN_TICKS_PER_STEP
            value = self._bar.value() + max(1, ui_scale.px(self._DOWN_STEP_PX))
            if value >= maximum:
                self._bar.setValue(maximum)
                self._phase = self._PAUSE_BOTTOM
                self._wait_ms = self._BOTTOM_PAUSE_MS
            else:
                self._bar.setValue(value)
            return
        value = self._bar.value() - max(1, ui_scale.px(self._UP_STEP_PX))
        if value <= 0:
            self._bar.setValue(0)
            self._phase = self._PAUSE_TOP
            self._wait_ms = self._TOP_PAUSE_MS
        else:
            self._bar.setValue(value)

    def _resumed_phase(self, maximum: int) -> str:
        """The direction to travel once a wait ends.

        After the bottom hold the cycle rewinds. After a manual scroll it
        reads onward from wherever the reader stopped, unless they are
        already at the end, in which case rewinding is the only way on.
        """
        if self._phase == self._PAUSE_BOTTOM:
            return self._UP
        if self._phase == self._MANUAL and self._bar.value() >= maximum:
            return self._UP
        return self._DOWN
