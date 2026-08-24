"""Keeping the sign-in screen up while the main window is built behind it.

Signing in used to leave the screen empty. The dialog closed the moment the
password was accepted and the main window appeared only once every tab had
been constructed, which on this machine is under three seconds and on a slower
one is longer. Nothing was on screen in between, so the application looked
like it had not started.

So the dialog stays. It swaps its form for a progress bar, reports each stage
of the build as it happens and closes only when there is a window to hand over
to. The user never sees nothing.

The bar is DETERMINATE and driven by real stages, not a busy animation. That
is not decoration: the build runs on the GUI thread, so an indeterminate bar
would be frozen for exactly as long as it was meant to reassure. Each report
repaints the one widget that changed, which is also what keeps the dialog
responsive enough to draw at all.

The bar takes the theme's accent, which is what `QProgressBar::chunk` is
already painted with: violet on the dark panel, purple on the light one. It is
the one colour in the palette that means identity rather than a verdict, which
is right for a bar that says nothing about the budget.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget

from clear_budget.ui import label_roles, ui_scale

_PREPARING_TEXT = "Preparing your budget…"
# Everything a user could do to the form while it is no longer a form.
_BLOCKED_EVENTS = (
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseButtonRelease,
    QEvent.Type.MouseButtonDblClick,
    QEvent.Type.KeyPress,
    QEvent.Type.KeyRelease,
)
# Room for the bar and its line of text, so adding them does not resize the
# dialog under the user at the moment it changes what it is showing.
_BAR_HEIGHT_PX = 14


class HandoverProgressMixin:
    """A sign-in dialog that stays up while the window behind it is built."""

    def install_handover_progress(self, layout: QVBoxLayout) -> None:
        """Add the hidden progress surface to `layout`; call while building."""
        self._handover = QWidget()
        self._handover.setVisible(False)
        box = QVBoxLayout(self._handover)
        box.setContentsMargins(0, 0, 0, 0)
        self._handover_label = QLabel(_PREPARING_TEXT)
        self._handover_label.setObjectName(label_roles.HINT)
        box.addWidget(self._handover_label)
        self._handover_bar = QProgressBar()
        self._handover_bar.setTextVisible(False)
        self._handover_bar.setFixedHeight(ui_scale.px(_BAR_HEIGHT_PX))
        self._handover_bar.setRange(0, 1)
        self._handover_bar.setValue(0)
        box.addWidget(self._handover_bar)
        layout.addWidget(self._handover)

    def begin_handover(self) -> None:
        """Show the dialog again, now as a progress surface.

        `accept()` has already hidden it, so this shows it a second time.

        The form is left exactly as it looks and is made INERT instead, by
        swallowing input rather than by disabling the widgets. Disabling was
        tried and is wrong here: a disabled control in this application wears
        the red ring of the three-state model, so the whole screen turned red
        at the moment it was meant to say "working". Red means broken; this
        is busy.

        Nothing is removed either. Taking the form out would resize the
        dialog and move it on screen at the one moment the user is watching
        it, for nothing gained.
        """
        self._handover_guard = _InputGuard(self)
        self.installEventFilter(self._handover_guard)
        QApplication.instance().installEventFilter(self._handover_guard)
        self._handover.setVisible(True)
        self.show()
        self.raise_()
        QApplication.processEvents()

    def report_progress(self, done: int, total: int, label: str = "") -> None:
        """Move the bar to `done` of `total`, then let the dialog repaint."""
        if not getattr(self, "_handover", None):
            return
        self._handover_bar.setRange(0, max(1, total))
        self._handover_bar.setValue(min(done, max(1, total)))
        if label:
            self._handover_label.setText(f"{_PREPARING_TEXT[:-1]}: {label}")
        QApplication.processEvents()

    def end_handover(self) -> None:
        """Close the sign-in screen for good, the window being ready.

        Safe to call twice. The caller ends the handover in a `finally`, so
        the ordinary path and a failing one can both reach here; a second
        call would otherwise touch a widget whose C++ side `deleteLater`
        plus `processEvents` has already destroyed, raising from a cleanup
        block that exists to keep the screen from being stranded.
        """
        if getattr(self, "_handover", None) is None:
            return
        guard = getattr(self, "_handover_guard", None)
        if guard is not None:
            QApplication.instance().removeEventFilter(guard)
            self.removeEventFilter(guard)
            self._handover_guard = None
        self._handover.setVisible(False)
        self._handover = None
        self.hide()
        self.deleteLater()
        QApplication.processEvents()


class _InputGuard(QObject):
    """Swallows input aimed at the sign-in screen while it is handing over.

    Scoped to that screen and its children: the filter is installed on the
    application so it sees events before the widgets do, then tests the
    target, so nothing else on screen is affected. Removed the moment the
    handover ends, which is also when the screen goes away.
    """

    def __init__(self, screen) -> None:
        super().__init__(screen)
        self._screen = screen

    def eventFilter(self, obj, event) -> bool:
        if event.type() not in _BLOCKED_EVENTS:
            return False
        if obj is self._screen or (
            isinstance(obj, QWidget) and self._screen.isAncestorOf(obj)
        ):
            return True
        return False
