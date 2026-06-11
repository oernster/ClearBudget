"""Formatting helpers for UI display."""

from pathlib import Path

MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _resolve_app_icon() -> Path | None:
    from clear_budget.shared.resources import iter_qt_window_icon_candidates

    for p in iter_qt_window_icon_candidates():
        if p.suffix.lower() == ".png":
            return p
    return None


_APP_ICON_PATH: Path | None = _resolve_app_icon()


def build_nav_month_widget(initial_text: str, prev_btn=None, next_btn=None):
    """Return (QWidget, QLabel) - centered icon + month label for nav rows.

    If `prev_btn`/`next_btn` are given, they are placed either side of the
    month label so the navigation buttons flank the title.
    """
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import Qt
    from clear_budget.ui import ui_scale

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    if prev_btn is not None:
        layout.addWidget(prev_btn)

    if _APP_ICON_PATH is not None:
        icon_height = prev_btn.sizeHint().height() if prev_btn is not None else 24
        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            QPixmap(str(_APP_ICON_PATH)).scaledToHeight(
                icon_height, Qt.TransformationMode.SmoothTransformation
            )
        )
        layout.addWidget(icon_lbl)

    month_lbl = QLabel(initial_text)
    month_lbl.setStyleSheet(
        ui_scale.style(
            "font-size: 20px; font-weight: bold; padding: 10px; color: #9ca3af;"
        )
    )
    month_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    layout.addWidget(month_lbl)

    if next_btn is not None:
        layout.addWidget(next_btn)

    return container, month_lbl


def fmt(amount: "int | float") -> str:
    """Format as a currency string using the active symbol.

    Pass pence as int (divided by 100 internally) or pounds as float (used directly).
    """
    from clear_budget.shared.currency import get_symbol

    sym = get_symbol()
    if isinstance(amount, int):
        return f"{sym}{amount / 100:.2f}"
    return f"{sym}{amount:.2f}"


def format_category(category: str) -> str:
    """Format category: replace underscores with spaces and capitalize."""
    singular_map = {
        "subscriptions": "subscription",
        "utilities": "utility",
    }
    formatted = singular_map.get(category, category)
    return formatted.replace("_", " ").title()
