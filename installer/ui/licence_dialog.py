"""Installer licence dialog.

Shows the full GNU LGPL v3 text in a vertically scrollable, read-only view
that reads itself: it holds still while the reader orients, descends at the
application's standard pace, holds at the end, rewinds and repeats. A licence
is the longest thing this program ever shows and the least likely to be
scrolled by hand, so it is precisely the surface the behaviour exists for: a
page to READ THROUGH rather than to act on.

The scroller is the APPLICATION'S, imported rather than copied. Fulcrum's
installer carries a standalone copy because it can import nothing from the
package it installs; this one already reads the application's launch screen
and its theme, so a second copy here would only be a second set of constants
free to drift from the first. The pace is the application's single reading
pace and no surface gets its own.

One deliberate difference: the installer never calls `ui_scale.init()`, so
the descent runs at a factor of 1.0. That is correct rather than overlooked.
The installer's layout is unscaled throughout, so a descent scaled to the
display would travel faster than the text it is reading.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
)

from clear_budget.ui.widgets.auto_scroller import AutoScroller
from installer.ui.lgpl3_license_text import LGPL_V3_TEXT


class InstallerLicenceDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Installer licence")
        self.setModal(True)
        # Delete on close to avoid stale windows accumulating.
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Large enough to read comfortably without being absurd on smaller
        # displays.
        self.resize(456, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # A QTextBrowser, NOT a QPlainTextEdit; the reason is the pace rather
        # than the rendering. QPlainTextEdit scrolls by LINES: its
        # scrollbar ran 0 to 137 for this entire licence, so a descent of one
        # unit every two ticks crossed the whole text in 11 seconds, which is
        # a blur and not a reading pass. A QTextBrowser scrolls by PIXELS and
        # the same text measures 2220, giving the 178 seconds the standard
        # pace is meant to take. Attaching the scroller to a line-scrolled
        # surface hands that one dialog a pace 16x the rest of the
        # application, which is exactly what having one set of constants
        # exists to prevent. This also matches the licence viewer the
        # application itself uses.
        text = QTextBrowser(self)
        text.setObjectName("LicenceText")
        text.setReadOnly(True)
        text.setPlainText(LGPL_V3_TEXT)
        text.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(text, 1)

        # Held on the dialog as well as parented to the surface: the scroller
        # is a QObject child of `text`, so Qt owns its lifetime and it goes
        # when this dialog is deleted on close, which is what WA_DeleteOnClose
        # above arranges.
        self._scroller = AutoScroller(text)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
