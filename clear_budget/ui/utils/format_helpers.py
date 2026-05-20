"""Formatting helpers for UI display."""

from pathlib import Path

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

def _resolve_app_icon() -> Path | None:
    from clear_budget.shared.resources import iter_qt_window_icon_candidates
    for p in iter_qt_window_icon_candidates():
        if p.suffix.lower() == '.png':
            return p
    return None

_APP_ICON_PATH: Path | None = _resolve_app_icon()


def build_nav_month_widget(initial_text: str):
    """Return (QWidget, QLabel) — centered icon + month label for nav rows."""
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import Qt
    from clear_budget.ui import ui_scale

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    if _APP_ICON_PATH is not None:
        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            QPixmap(str(_APP_ICON_PATH)).scaledToHeight(
                24, Qt.TransformationMode.SmoothTransformation
            )
        )
        layout.addWidget(icon_lbl)

    month_lbl = QLabel(initial_text)
    month_lbl.setStyleSheet(
        ui_scale.style("font-size: 20px; font-weight: bold; padding: 10px; color: #9ca3af;")
    )
    month_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    layout.addWidget(month_lbl)

    return container, month_lbl


def format_category(category: str) -> str:
    """Format category: replace underscores with spaces and capitalize."""
    singular_map = {
        "subscriptions": "subscription",
        "utilities": "utility",
    }
    formatted = singular_map.get(category, category)
    return formatted.replace("_", " ").title()
