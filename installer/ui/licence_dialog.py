"""Installer licence dialog.

Shows the full GNU LGPL v3 text in a vertically scrollable, read-only view.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout

from installer.ui.lgpl3_license_text import LGPL_V3_TEXT


class InstallerLicenceDialog(QDialog):
    def __init__(self, parent=None) -> None:  # noqa: ANN001 (Qt API)
        super().__init__(parent)

        self.setWindowTitle("Installer licence")
        self.setModal(True)
        # Delete on close to avoid stale windows accumulating.
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Large enough to read comfortably, but not absurd on smaller displays.
        self.resize(456, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        text = QPlainTextEdit(self)
        text.setObjectName("LicenceText")
        text.setReadOnly(True)
        text.setPlainText(LGPL_V3_TEXT)
        text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
