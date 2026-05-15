from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from clear_budget.version import APP_NAME, APP_AUTHOR, APP_COPYRIGHT, __version__


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setModal(True)
        self.setFixedSize(400, 300)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Icon + Title + Version row
        header_layout = QHBoxLayout()

        # Icon (128px)
        icon_label = QLabel()
        icon_path = (
            Path(__file__).resolve().parents[3] / "ClearBudget_128.png"
        )
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            icon_label.setPixmap(
                pixmap.scaledToWidth(
                    64, Qt.TransformationMode.SmoothTransformation
                )
            )
        header_layout.addWidget(icon_label)

        # Title + Version
        text_layout = QVBoxLayout()
        title = QLabel(f"<b style='font-size: 18px;'>{APP_NAME}</b>")
        version = QLabel(f"<span style='font-size: 13px; color: #999;'>v{__version__}</span>")
        version.setTextFormat(1)  # Rich text
        text_layout.addWidget(title)
        text_layout.addWidget(version)
        text_layout.addStretch()
        header_layout.addLayout(text_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Description
        desc = QLabel(
            "A personal budget planner for forward-looking spending forecasts "
            "with credit card tracking and solvency warnings."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; color: #aaa; line-height: 1.5;")
        layout.addWidget(desc)

        # Copyright
        copyright_label = QLabel(APP_COPYRIGHT)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("font-size: 11px; color: #666; margin-top: 10px;")
        layout.addWidget(copyright_label)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)
