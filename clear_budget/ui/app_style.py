"""The application's style: prompt tooltips and label insets, app-wide.

Two things belong to the STYLE rather than to any one widget, so both live in
one proxy style wrapping whatever style the platform chose, installed once at
each composition root (the app's `startup.begin` and the installer's `main`).
No widget opts in to either.

Tooltips. Qt shows a tooltip only after the style's wake-up delay and the
platform default is 700ms (measured against this venv's Qt via
`QStyle.SH_ToolTip_WakeUpDelay`). Worse than the number suggests: any mouse
movement inside the control restarts the timer, so in practice the hover text
on the icon buttons took a second or two to appear.

The same install also makes tooltips appear while another program has focus.
Qt Widgets shows a tooltip only over the active window unless that window
carries `WA_AlwaysShowToolTips`; measured on the real Windows platform with
the cursor moved over an inactive window, the tip stayed hidden without the
attribute and appeared with it. The attribute belongs to each top-level
window, dialogs and message boxes included, so an application-wide filter
sets it on every window as it is shown rather than each window opting in.

Label insets. A label's inset is applied here as contents margins whenever it
is polished, from the table in label_insets, which says why a stylesheet
cannot carry it. Polish is the one moment every label passes through: when
it is built, when set_role swaps its role and when a theme is applied.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QLabel, QProxyStyle, QStyle, QWidget

from clear_budget.ui.label_insets import inset_for

# Short enough to read as immediate on an intentional pause, long enough
# that sweeping the cursor across a tray of icon buttons does not flash
# every tooltip on the way past.
TOOLTIP_WAKE_DELAY_MS = 100
# Marks a label whose margins this style set, so a later role without an
# inset clears them; margins set any other way are never touched.
_INSET_BY_STYLE = "clearbudgetInsetByStyle"
_NO_INSET = (0, 0, 0, 0)


class _AppStyle(QProxyStyle):
    """The platform style with prompt tooltips and role-driven label insets."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return TOOLTIP_WAKE_DELAY_MS
        return super().styleHint(hint, option, widget, returnData)

    def polish(self, arg):
        if isinstance(arg, QLabel):
            _apply_inset(arg)
        return super().polish(arg)


def _apply_inset(label: QLabel) -> None:
    inset = inset_for(label.objectName())
    if inset is not None:
        label.setContentsMargins(*inset)
        label.setProperty(_INSET_BY_STYLE, True)
    elif label.property(_INSET_BY_STYLE):
        label.setContentsMargins(*_NO_INSET)
        label.setProperty(_INSET_BY_STYLE, False)


class _TooltipsOnInactiveWindows(QObject):
    """Marks every top-level window as it is shown so its tooltips always show."""

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt naming)
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QWidget)
            and watched.isWindow()
        ):
            watched.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        return False


def install(app) -> None:
    """Give `app` prompt tooltips (shown over inactive windows too) plus insets.

    Wrapping by style KEY rather than by object: handing the live style
    object to the proxy would leave two owners of one QStyle when the
    application replaces it, so the proxy builds its own base instance
    from the same factory key. The filter is parented to `app`, which keeps
    it alive for the application's lifetime.
    """
    app.setStyle(_AppStyle(app.style().objectName()))
    app.installEventFilter(_TooltipsOnInactiveWindows(app))
