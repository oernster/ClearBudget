from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from clear_budget.version import APP_NAME, __version__

from installer.ui._safe_label import SafeLabel


def build_installer_main_window_ui(window: Any) -> None:
    """Build and attach the installer window UI.

    Extracted to keep [`InstallerMainWindow`](installer/ui/main_window.py:48)
    under the hard <=400 LOC limit.
    """

    root = QWidget(window)
    window.setCentralWidget(root)

    outer = QVBoxLayout(root)
    outer.setContentsMargins(36, 24, 36, 20)
    outer.setSpacing(16)

    header_row = QHBoxLayout()
    header_row.setSpacing(12)

    # NOTE: This header is intentionally over-allocated by a few pixels.
    # On some Windows DPI/font combinations, Qt can clip the last glyph by 1-2px
    # even when it wouldn't elide. This safety buffer enforces the hard
    # requirement of *zero truncation*.
    title = SafeLabel(
        f"{APP_NAME} Setup",
        extra_width_px=150,
        extra_height_px=18,
        # Bias rendering slightly up-left to avoid descender/edge clipping.
        draw_dx_px=-1,
        draw_dy_px=-1,
    )
    title.setObjectName("HeaderTitle")
    title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    version = SafeLabel(f"v{__version__}", extra_width_px=2, extra_height_px=2)
    version.setObjectName("HeaderVersion")
    version.setAlignment(Qt.AlignVCenter)
    version.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

    # Keep references for runtime sizing logic (DPI/accessibility variability).
    window._header_title = title
    window._header_version = version

    header_left = QHBoxLayout()
    header_left.setSpacing(14)
    header_left.addWidget(title)
    header_left.addWidget(version)

    window._licence_btn = QPushButton("Licence")
    window._licence_btn.setObjectName("LicenceButton")
    window._licence_btn.setToolTip("Installer licence")

    window._theme_toggle_btn = QPushButton(window._theme.toggle_label)  # noqa: SLF001
    window._theme_toggle_btn.setObjectName("ThemeToggle")

    # Give the left side stretch so the header title has priority in width
    # allocation (prevents font-metric rounding causing clipping). Do not add an
    # extra stretch item, otherwise the free space is split and the title can be
    # under-allocated on some DPI/font configurations.
    header_row.addLayout(header_left, 1)
    header_row.addWidget(window._licence_btn)
    header_row.addWidget(window._theme_toggle_btn)

    outer.addLayout(header_row)

    window._subtitle = SafeLabel(
        f"Welcome to the {APP_NAME} Installer", extra_width_px=8, extra_height_px=6
    )
    window._subtitle.setObjectName("SubTitle")
    window._subtitle.setAlignment(Qt.AlignHCenter)
    window._subtitle.setWordWrap(True)
    outer.addWidget(window._subtitle)

    window._status_line = SafeLabel("", extra_width_px=6, extra_height_px=6)
    window._status_line.setObjectName("StatusLine")
    window._status_line.setWordWrap(True)
    window._status_line.setAlignment(Qt.AlignHCenter)
    outer.addWidget(window._status_line)

    # Install directory picker row (always present; used for install/upgrade/reinstall)
    dir_row = QHBoxLayout()
    dir_row.setSpacing(10)

    window._install_dir_edit = QLineEdit()
    window._install_dir_edit.setPlaceholderText("Installation directory")
    window._install_dir_edit.setText(str(window._default_install_dir()))  # noqa: SLF001

    browse = QPushButton("Browse")
    browse.setObjectName("BrowseButton")
    dir_row.addWidget(window._install_dir_edit, 1)
    dir_row.addWidget(browse)
    outer.addLayout(dir_row)

    window._desktop_cb = QCheckBox("Create desktop shortcut")
    window._desktop_cb.setChecked(True)
    window._startmenu_cb = QCheckBox("Create Start menu shortcut")
    window._startmenu_cb.setChecked(True)
    outer.addWidget(window._desktop_cb)
    outer.addWidget(window._startmenu_cb)

    outer.addSpacing(10)

    window._actions_row = QHBoxLayout()
    window._actions_row.setSpacing(18)

    window._actions_row.addStretch(1)

    window._btn_primary_left = QPushButton("Install")
    window._btn_primary_left.setObjectName("PrimaryAction")

    window._btn_primary_right = QPushButton("Repair")
    window._btn_primary_right.setObjectName("PrimaryAction")

    window._actions_row.addWidget(window._btn_primary_left)
    window._actions_row.addWidget(window._btn_primary_right)
    window._actions_row.addStretch(1)
    outer.addLayout(window._actions_row)

    window._btn_uninstall = QPushButton("Uninstall")
    window._btn_uninstall.setObjectName("DangerAction")
    outer.addWidget(window._btn_uninstall, alignment=Qt.AlignHCenter)

    # Keep the bottom area visually balanced (avoid a huge empty gap).
    outer.addStretch(0)

    window._progress_bar = QProgressBar()
    window._progress_bar.setObjectName("ProgressBar")
    window._progress_bar.setTextVisible(False)
    window._progress_bar.setRange(0, 100)
    window._progress_bar.setValue(0)
    window._progress_bar.setVisible(False)
    outer.addWidget(window._progress_bar)

    window._progress = SafeLabel("", extra_width_px=6, extra_height_px=6)
    window._progress.setObjectName("StatusLine")
    window._progress.setAlignment(Qt.AlignHCenter)
    outer.addWidget(window._progress)

    # Return the browse button so the caller can connect signals.
    window._browse_btn = browse
