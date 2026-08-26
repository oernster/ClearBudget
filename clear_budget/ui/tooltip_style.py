"""Prompt tooltips, application-wide.

Qt shows a tooltip only after the style's wake-up delay and the platform
default is 700ms (measured against this venv's Qt via
`QStyle.SH_ToolTip_WakeUpDelay`). Worse than the number suggests: any mouse
movement inside the control restarts the timer, so in practice the hover text
on the icon buttons took a second or two to appear.

The delay is a STYLE HINT, not a per-widget property, so the fix is one
proxy style wrapping whatever style the platform chose, installed once at
each composition root (the app's `startup.begin` and the installer's
`main`). Every tooltip in the program is covered; no widget opts in.
"""

from __future__ import annotations

from PySide6.QtWidgets import QProxyStyle, QStyle

# Short enough to read as immediate on an intentional pause, long enough
# that sweeping the cursor across a tray of icon buttons does not flash
# every tooltip on the way past.
TOOLTIP_WAKE_DELAY_MS = 100


class _PromptTooltipStyle(QProxyStyle):
    """The platform style with one hint changed: tooltips wake quickly."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return TOOLTIP_WAKE_DELAY_MS
        return super().styleHint(hint, option, widget, returnData)


def install(app) -> None:
    """Wrap `app`'s current style so tooltips appear promptly.

    Wrapping by style KEY rather than by object: handing the live style
    object to the proxy would leave two owners of one QStyle when the
    application replaces it, so the proxy builds its own base instance
    from the same factory key.
    """
    app.setStyle(_PromptTooltipStyle(app.style().objectName()))
