from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from clear_budget.version import APP_NAME, __version__
from installer.ui._safe_label import SafeLabel
from installer.ui._theme_toggle import apply_toggle_face


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
        # Centre the TITLE on its ink rather than on its line box, so it reads
        # level with the version and the two buttons beside it. See
        # SafeLabel.ink_offset_px: at 38px the difference measured 8px.
        centre_on_ink=True,
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

    # Vertical centring is stated on every item in this row rather than left
    # to the layout. Without it each widget was laid from the TOP of a row
    # sized by the tallest of them, so the title's box centred 13px below the
    # buttons' before its ink had even been considered. Only the VERTICAL
    # flag is given: adding a horizontal one would stop the title expanding
    # and put the zero-truncation guarantee above back at risk.
    header_left = QHBoxLayout()
    header_left.setSpacing(14)
    header_left.addWidget(title, 0, Qt.AlignVCenter)
    header_left.addWidget(version, 0, Qt.AlignVCenter)

    window._licence_btn = QPushButton("Licence")
    window._licence_btn.setObjectName("LicenceButton")
    window._licence_btn.setToolTip("Installer licence")

    window._theme_toggle_btn = QPushButton()
    window._theme_toggle_btn.setObjectName("ThemeToggle")
    apply_toggle_face(window._theme_toggle_btn, window._theme)

    # Give the left side stretch so the header title has priority in width
    # allocation (prevents font-metric rounding causing clipping). Do not add an
    # extra stretch item, otherwise the free space is split and the title can be
    # under-allocated on some DPI/font configurations.
    header_row.addLayout(header_left, 1)
    header_row.addWidget(window._licence_btn, 0, Qt.AlignVCenter)
    header_row.addWidget(window._theme_toggle_btn, 0, Qt.AlignVCenter)

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
    window._install_dir_edit.setText(str(window._default_install_dir()))

    browse = QPushButton("Browse")
    browse.setObjectName("BrowseButton")
    dir_row.addWidget(window._install_dir_edit, 1)
    dir_row.addWidget(browse)
    outer.addLayout(dir_row)

    window._desktop_cb = QCheckBox("Create desktop shortcut")
    window._desktop_cb.setChecked(True)
    window._startmenu_cb = QCheckBox("Create Start menu shortcut")
    window._startmenu_cb.setChecked(True)
    # Acted on after a successful install, upgrade or reinstall; ignored by
    # repair and uninstall, neither of which leaves anything new to launch.
    window._launch_cb = QCheckBox(f"Launch {APP_NAME} when setup finishes")
    window._launch_cb.setChecked(True)
    outer.addWidget(window._desktop_cb)
    outer.addWidget(window._startmenu_cb)
    outer.addWidget(window._launch_cb)

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
    # Hidden, yet it must still OCCUPY its space. Without this the bar's height
    # left the layout whenever it was hidden, so the whole column below the
    # status line jumped up the moment an operation started and dropped back
    # when it finished: the buttons moved under the pointer mid-install.
    _bar_policy = window._progress_bar.sizePolicy()
    _bar_policy.setRetainSizeWhenHidden(True)
    window._progress_bar.setSizePolicy(_bar_policy)
    outer.addWidget(window._progress_bar)

    window._progress = SafeLabel("", extra_width_px=6, extra_height_px=6)
    window._progress.setObjectName("StatusLine")
    window._progress.setAlignment(Qt.AlignHCenter)
    # Pinned to one line for the same reason: this label alternates between a
    # worker message and an empty string; an empty QLabel is shorter than
    # a filled one, so its height would move everything above it.
    window._progress.setFixedHeight(window._progress.line_height())
    outer.addWidget(window._progress)

    # Return the browse button so the caller can connect signals.
    window._browse_btn = browse
