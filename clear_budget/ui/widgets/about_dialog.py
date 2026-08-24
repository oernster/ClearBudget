"""About and Licence dialogs for ClearBudget."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from clear_budget.ui import ui_scale
from clear_budget.ui.widgets.auto_scroller import AutoScroller
from clear_budget.ui.widgets.first_stop_dialog import FirstStopDialog
from clear_budget.version import __version__ as _APP_VERSION


def _resolve_about_icon() -> Path | None:
    from clear_budget.shared.resources import find_logo_png_path

    return find_logo_png_path()


_ICON_PATH: Path | None = _resolve_about_icon()

# True only on Windows, where pywin32 is an actual runtime dependency. On macOS
# and Linux it is neither bundled nor used, so its attribution is omitted there.
# The same per-platform rule covers keyring's backends: pywin32-ctypes ships
# only on Windows, SecretStorage/Jeepney/cryptography only on Linux; the macOS
# backend is pure ctypes against the system Security framework.
_IS_WINDOWS = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")

# Open source credits as discrete HTML <li> items so platform-specific entries
# (pywin32) can be filtered and so no stray source comments leak into the
# rendered dialog text.
# Components SHIPPED inside the application, listed first because these are
# the ones whose licences travel with the binary. Checked against what the
# build actually bundles (PySide6, shiboken6, bcrypt, keyring and the native
# sqlite3/libcrypto/libssl/libffi libraries), not against requirements.txt,
# which lists neither the transitive native libraries nor shiboken6.
_SHIPPED: list[str] = [
    (
        "<li><b>Python</b> - Copyright &copy; 2001&ndash;2025 Python Software "
        "Foundation. Licensed under the PSF Licence.</li>"
    ),
    (
        "<li><b>PySide6 (Qt for Python)</b> - Copyright &copy; The Qt Company "
        "Ltd. Licensed under LGPL-3.0.</li>"
    ),
    (
        "<li><b>Shiboken6</b> - Copyright &copy; The Qt Company Ltd. The "
        "binding runtime PySide6 is built on. Licensed under LGPL-3.0.</li>"
    ),
    (
        "<li><b>SQLite</b> - Dedicated to the public domain by D. Richard Hipp "
        "and contributors.</li>"
    ),
    (
        "<li><b>OpenSSL</b> - Copyright &copy; The OpenSSL Project Authors. "
        "Provides the cryptographic libraries Python links against. Licensed "
        "under the Apache Licence 2.0.</li>"
    ),
    (
        "<li><b>libffi</b> - Copyright &copy; Anthony Green and contributors. "
        "Licensed under an MIT-style licence.</li>"
    ),
    (
        "<li><b>bcrypt</b> - Copyright &copy; Nate Lawson, Perry Metzger and "
        "contributors. Licensed under the Apache Licence 2.0.</li>"
    ),
    (
        "<li><b>keyring</b> - Copyright &copy; Jason R. Coombs and "
        "contributors. Stores the remembered sign-in in the operating "
        "system's own credential store. Licensed under the MIT Licence.</li>"
    ),
]
if _IS_WINDOWS:
    _SHIPPED.append(
        "<li><b>pywin32</b> - Copyright &copy; Mark Hammond. Licensed under "
        "the PSF Licence.</li>"
    )
    _SHIPPED.append(
        "<li><b>pywin32-ctypes</b> - Copyright &copy; Enthought, Inc. The "
        "Windows Credential Manager binding keyring uses. Licensed under a "
        "BSD-style licence.</li>"
    )
if _IS_LINUX:
    _SHIPPED.append(
        "<li><b>SecretStorage</b> - Copyright &copy; Dmitry Shachnev and "
        "contributors. The Secret Service binding keyring uses. Licensed "
        "under the BSD-3-Clause Licence.</li>"
    )
    _SHIPPED.append(
        "<li><b>Jeepney</b> - Copyright &copy; Thomas Kluyver and "
        "contributors. The DBus transport SecretStorage is built on. "
        "Licensed under the MIT Licence.</li>"
    )
    _SHIPPED.append(
        "<li><b>cryptography</b> - Copyright &copy; The Python Cryptographic "
        "Authority and contributors. Used by SecretStorage. Licensed under "
        "Apache-2.0 or BSD-3-Clause.</li>"
    )

# Tools used to BUILD and verify the application. They are not shipped, so
# they are courtesy rather than obligation but the work is no less owed.
_TOOLING: list[str] = [
    (
        "<li><b>PyInstaller</b> - Copyright &copy; 2010&ndash;2025 PyInstaller "
        "contributors. Licensed under GPL-2.0 with a bootloader exception for "
        "bundled applications.</li>"
    ),
    (
        "<li><b>Pillow</b> - Copyright &copy; Jeffrey A. Clark and "
        "contributors. Builds the application icons. Licensed under the "
        "HPND (MIT-CMU) licence.</li>"
    ),
    (
        "<li><b>pytest</b> - Copyright &copy; 2004&ndash;2025 Holger Krekel and "
        "pytest contributors. Licensed under the MIT Licence.</li>"
    ),
    (
        "<li><b>pytest-qt</b> - Copyright &copy; Bruno Oliveira and "
        "contributors. Licensed under the MIT Licence.</li>"
    ),
    (
        "<li><b>pytest-cov</b> - Copyright &copy; Marc Schlaich and "
        "contributors. Licensed under the MIT Licence.</li>"
    ),
    (
        "<li><b>coverage.py</b> - Copyright &copy; Ned Batchelder and "
        "contributors. Licensed under the Apache Licence 2.0.</li>"
    ),
    (
        "<li><b>black</b> - Copyright &copy; 2018&ndash;2025 Łukasz Langa and "
        "contributors. Licensed under the MIT Licence.</li>"
    ),
    (
        "<li><b>Flake8</b> - Copyright &copy; Tarek Ziad&eacute;, Ian Stapleton "
        "Cordasco and contributors. Licensed under the MIT Licence.</li>"
    ),
    (
        "<li><b>Ruff</b> - Copyright &copy; Astral Software Inc. Licensed "
        "under the MIT Licence.</li>"
    ),
]

_CREDITS: list[str] = _SHIPPED + _TOOLING

_SHIPPED_HTML = "\n".join(_SHIPPED)
_TOOLING_HTML = "\n".join(_TOOLING)

_ABOUT_TEXT = f"""\
<h2>ClearBudget</h2>
<p><b>Personal Budgeting and Solvency Forecasting</b></p>
<p><b>Version:</b> {_APP_VERSION}</p>
<p><b>Author:</b> Oliver Ernster</p>
<p>Distributed under the GNU Lesser General Public Licence v3.0 (LGPL-3.0).</p>
<hr>
<h3>Open Source Credits</h3>
<p>ClearBudget is built on the shoulders of the following open source projects
and their communities:</p>
<p><b>Bundled with the application</b>, so their licences travel with it:</p>
<ul>
{_SHIPPED_HTML}
</ul>
<p><b>Used to build and test it</b>, not shipped but no less owed:</p>
<ul>
{_TOOLING_HTML}
</ul>
<p>My thanks to the Python community for providing an outstanding ecosystem
that makes projects like this possible.</p>
"""

_LGPL3_NOTICE_HEAD = (
    "GNU LESSER GENERAL PUBLIC LICENCE\n"
    "Version 3, 29 June 2007\n"
    "\n"
    "ClearBudget - Personal Budget Planner\n"
    "Copyright (C) 2025 Oliver Ernster\n"
    "\n"
    # The two paragraphs below are the FSF's own notice, reproduced as the
    # licence requires. Their punctuation is part of the quotation, so the
    # house comma rule does not reach them; rewriting it would misquote.
    "This program is free software: you can redistribute it and/or modify it under the terms of the GNU Lesser General Public Licence as published by the Free Software Foundation, either version 3 of the Licence, or (at your option) any later version.\n"  # prose-sweep: allow
    "\n"
    "This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public Licence for more details.\n"  # prose-sweep: allow
    "\n"
    "You should have received a copy of the GNU Lesser General Public Licence along with this program. If not, see <https://www.gnu.org/licenses/>.\n"
    "\n"
    "----------------------------------------\n"
    "\n"
    "The full licence text is available at:\n"
    "\n"
    "    https://www.gnu.org/licenses/lgpl-3.0.html\n"
    "\n"
    "Key terms summary:\n"
    "  • You may use, copy, modify and distribute this software under LGPL-3.0.\n"
    "  • If you distribute modified versions of this software, you must make the modified source available under the same licence.\n"
    "  • You must allow end users to replace or relink the LGPL-licensed libraries (PySide6 / Qt) used by this application.\n"
    "  • There is NO WARRANTY for this program, to the extent permitted by law.\n"
    "\n"
    "----------------------------------------\n"
    "\n"
    "THIRD-PARTY LIBRARY LICENCES\n"
    "\n"
)

# Third-party licence blocks, joined by a blank line. pywin32 is included only
# on Windows so the notice matches what is actually shipped on each platform.
_THIRD_PARTY_LICENCES: list[str] = [
    (
        "PySide6 (Qt for Python) - LGPL-3.0\n"
        "  https://www.gnu.org/licenses/lgpl-3.0.html\n"
    ),
    (
        "Python Standard Library - PSF Licence\n"
        "  https://docs.python.org/3/license.html\n"
    ),
    "SQLite - Public Domain\n  https://www.sqlite.org/copyright.html\n",
    "bcrypt - Apache Licence 2.0\n  https://www.apache.org/licenses/LICENSE-2.0\n",
    "keyring - MIT Licence\n  https://opensource.org/licenses/MIT\n",
    "pytest - MIT Licence\n  https://opensource.org/licenses/MIT\n",
    "black - MIT Licence\n  https://opensource.org/licenses/MIT\n",
]
if _IS_WINDOWS:
    _THIRD_PARTY_LICENCES.append(
        "pywin32 - PSF Licence\n"
        "  https://github.com/mhammond/pywin32/blob/main/LICENCE.txt\n"
    )
_THIRD_PARTY_LICENCES.append(
    "PyInstaller - GPL-2.0 with bootloader exception\n"
    "  https://pyinstaller.org/en/stable/license.html\n"
)

_LGPL3_NOTICE = _LGPL3_NOTICE_HEAD + "\n".join(_THIRD_PARTY_LICENCES)


class AboutDialog(FirstStopDialog):
    """About ClearBudget dialog showing author, icon and library credits."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About ClearBudget")
        self.setMinimumWidth(ui_scale.px(540))
        layout = QVBoxLayout()
        layout.setSpacing(ui_scale.px(8))

        if _ICON_PATH is not None:
            icon_lbl = QLabel()
            pixmap = QPixmap(str(_ICON_PATH)).scaled(
                ui_scale.px(96),
                ui_scale.px(96),
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
        self._credits_scroller = AutoScroller(body)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        close_btn.clicked.connect(self.accept)


class LicenceDialog(FirstStopDialog):
    """Displays the LGPL-3.0 licence notice and third-party attributions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Licence - LGPL-3.0")
        self.setMinimumSize(ui_scale.px(680), ui_scale.px(520))
        layout = QVBoxLayout()

        browser = QTextBrowser()
        browser.setPlainText(_LGPL3_NOTICE)
        browser.setOpenExternalLinks(True)
        browser.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        layout.addWidget(browser)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        close_btn.clicked.connect(self.accept)
