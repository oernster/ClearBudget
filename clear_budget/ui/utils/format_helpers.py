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

# Cache for the icon pixmap, cropped to its opaque content (the source PNG
# has uneven transparent margins, which otherwise throws off the spacing
# between the icon and the surrounding nav widgets).
_ICON_PIXMAP_CACHE = None
_ICON_LOAD_ATTEMPTED = False


def _opaque_bounding_rect(image):
    """Return the QRect bounding box of non-transparent pixels in `image`."""
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QImage

    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()

    def row_has_content(y: int) -> bool:
        return any((image.pixel(x, y) >> 24) & 0xFF for x in range(width))

    def col_has_content(x: int) -> bool:
        return any((image.pixel(x, y) >> 24) & 0xFF for y in range(height))

    top = next((y for y in range(height) if row_has_content(y)), 0)
    bottom = next(
        (y for y in range(height - 1, -1, -1) if row_has_content(y)), height - 1
    )
    left = next((x for x in range(width) if col_has_content(x)), 0)
    right = next((x for x in range(width - 1, -1, -1) if col_has_content(x)), width - 1)
    return QRect(left, top, right - left + 1, bottom - top + 1)


def _load_cropped_icon_pixmap():
    """Return the app icon pixmap cropped to its opaque bounding box, or None."""
    global _ICON_PIXMAP_CACHE, _ICON_LOAD_ATTEMPTED
    if _ICON_LOAD_ATTEMPTED:
        return _ICON_PIXMAP_CACHE
    _ICON_LOAD_ATTEMPTED = True

    from PySide6.QtGui import QImage, QPixmap

    if _APP_ICON_PATH is None:
        return None
    image = QImage(str(_APP_ICON_PATH))
    if image.isNull():
        return None
    cropped = image.copy(_opaque_bounding_rect(image))
    _ICON_PIXMAP_CACHE = QPixmap.fromImage(cropped)
    return _ICON_PIXMAP_CACHE


def build_nav_month_widget(initial_text: str, prev_btn=None, next_btn=None):
    """Return (QWidget, QLabel) - centered icon + month label for nav rows.

    If `prev_btn`/`next_btn` are given, they are placed either side of the
    month label so the navigation buttons flank the title.
    """
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
    from PySide6.QtCore import Qt
    from clear_budget.ui import ui_scale

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    if prev_btn is not None:
        layout.addWidget(prev_btn)

    icon_pixmap = _load_cropped_icon_pixmap()
    if icon_pixmap is not None:
        icon_height = prev_btn.sizeHint().height() if prev_btn is not None else 24
        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            icon_pixmap.scaledToHeight(
                icon_height, Qt.TransformationMode.SmoothTransformation
            )
        )
        # Match the month label's own 10px padding, so the gap before the
        # icon equals the gap after the year (before the next/prev buttons).
        icon_lbl.setContentsMargins(10, 0, 0, 0)
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
