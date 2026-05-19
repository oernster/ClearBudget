"""About and Licence dialogs for ClearBudget."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtCore import QUrl

from clear_budget.ui import ui_scale

_ICON_PATH = Path(__file__).parents[3] / "ClearBudget.png"

_ABOUT_TEXT = """\
<h2>ClearBudget</h2>
<p><b>Personal Budget Planner</b></p>
<p><b>Author:</b> Oliver Ernster</p>
<p>Distributed under the GNU Lesser General Public Licence v3.0 (LGPL-3.0).</p>
<hr>
<h3>Open Source Credits</h3>
<p>ClearBudget is built on the shoulders of the following open source projects
and their communities:</p>
<ul>
  <li><b>Python</b> &mdash; Copyright &copy; 2001&ndash;2025 Python Software Foundation.
      Licensed under the PSF Licence.</li>
  <li><b>PySide6 (Qt for Python)</b> &mdash; Copyright &copy; The Qt Company Ltd.
      Licensed under LGPL-3.0.</li>
  <li><b>SQLite</b> &mdash; Dedicated to the public domain by D. Richard Hipp and contributors.</li>
  <li><b>pytest</b> &mdash; Copyright &copy; 2004&ndash;2025 Holger Krekel and pytest contributors.
      Licensed under the MIT Licence.</li>
  <li><b>black</b> &mdash; Copyright &copy; 2018&ndash;2025 &Lstrok;ukasz Langa and contributors.
      Licensed under the MIT Licence.</li>
  <li><b>pywin32</b> &mdash; Copyright &copy; Mark Hammond. Licensed under the PSF Licence.</li>
  <li><b>PyInstaller</b> &mdash; Copyright &copy; 2010&ndash;2025 PyInstaller contributors.
      Licensed under GPL-2.0 with a classpath exception for bundled applications.</li>
</ul>
<p>My thanks to the Python community for providing an outstanding ecosystem
that makes projects like this possible.</p>
"""

_LGPL3_NOTICE = """\
GNU LESSER GENERAL PUBLIC LICENCE
Version 3, 29 June 2007

ClearBudget — Personal Budget Planner
Copyright (C) 2025 Oliver Ernster

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public Licence as published by the Free
Software Foundation, either version 3 of the Licence, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public Licence for more
details.

You should have received a copy of the GNU Lesser General Public Licence along
with this program. If not, see <https://www.gnu.org/licenses/>.

────────────────────────────────────────────────────────────────────────────────

The full licence text is available at:

    https://www.gnu.org/licenses/lgpl-3.0.html

Key terms summary:
  • You may use, copy, modify, and distribute this software under LGPL-3.0.
  • If you distribute modified versions of this software, you must make the
    modified source available under the same licence.
  • You must allow end users to replace or relink the LGPL-licensed libraries
    (PySide6 / Qt) used by this application.
  • There is NO WARRANTY for this program, to the extent permitted by law.

────────────────────────────────────────────────────────────────────────────────

THIRD-PARTY LIBRARY LICENCES

PySide6 (Qt for Python) — LGPL-3.0
  https://www.gnu.org/licenses/lgpl-3.0.html

Python Standard Library — PSF Licence
  https://docs.python.org/3/license.html

SQLite — Public Domain
  https://www.sqlite.org/copyright.html

pytest — MIT Licence
  https://opensource.org/licenses/MIT

black — MIT Licence
  https://opensource.org/licenses/MIT

pywin32 — PSF Licence
  https://github.com/mhammond/pywin32/blob/main/LICENCE.txt

PyInstaller — GPL-2.0 with bootloader exception
  https://pyinstaller.org/en/stable/license.html
"""


class AboutDialog(QDialog):
    """About ClearBudget dialog showing author, icon, and library credits."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About ClearBudget")
        self.setMinimumWidth(ui_scale.px(540))
        layout = QVBoxLayout()
        layout.setSpacing(ui_scale.px(8))

        if _ICON_PATH.exists():
            icon_lbl = QLabel()
            pixmap = QPixmap(str(_ICON_PATH)).scaled(
                ui_scale.px(96), ui_scale.px(96),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_lbl.setPixmap(pixmap)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_lbl)

        body = QTextBrowser()
        body.setOpenExternalLinks(True)
        body.setHtml(_ABOUT_TEXT)
        body.setMinimumHeight(ui_scale.px(340))
        body.setStyleSheet("QTextBrowser { border: none; background: transparent; }")
        layout.addWidget(body)

        btn_row = QHBoxLayout()
        licence_btn = QPushButton("View Licence (LGPL-3.0)")
        close_btn = QPushButton("Close")
        btn_row.addWidget(licence_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        licence_btn.clicked.connect(self._open_licence)
        close_btn.clicked.connect(self.accept)

    def _open_licence(self) -> None:
        LicenceDialog(self).exec()


class LicenceDialog(QDialog):
    """Displays the LGPL-3.0 licence notice and third-party attributions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Licence — LGPL-3.0")
        self.setMinimumSize(ui_scale.px(680), ui_scale.px(520))
        layout = QVBoxLayout()

        browser = QTextBrowser()
        browser.setPlainText(_LGPL3_NOTICE)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)

        btn_row = QHBoxLayout()
        full_text_btn = QPushButton("Open Full Licence Text (gnu.org)")
        close_btn = QPushButton("Close")
        btn_row.addWidget(full_text_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        full_text_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.gnu.org/licenses/lgpl-3.0.html"))
        )
        close_btn.clicked.connect(self.accept)
