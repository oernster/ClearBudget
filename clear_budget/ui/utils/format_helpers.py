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


# Neutral colour for a nav month/year label before any solvency-driven colour
# is applied. The Solvency tab overrides this with a health colour and
# broadcasts it so every tab's nav label stays consistent.
NAV_LABEL_DEFAULT_COLOR = "#9ca3af"


def _nav_label_style(color: str) -> str:
    """Return the standard nav month/year label stylesheet in `color`.

    The base style (size/weight/padding) is fixed; only the colour varies, so
    a label can be recoloured without dropping its other properties.
    """
    from clear_budget.ui import ui_scale

    return ui_scale.style(
        f"font-size: 20px; font-weight: bold; padding: 10px; color: {color};"
    )


def apply_nav_label_color(label, color: str) -> None:
    """Recolour a nav month/year label, preserving its base style."""
    label.setStyleSheet(_nav_label_style(color))


def build_nav_month_widget(initial_text: str, prev_btn=None, next_btn=None):
    """Return (QWidget, QLabel) - centered icon + month label for nav rows.

    If `prev_btn`/`next_btn` are given, they are placed either side of the
    month label so the navigation buttons flank the title.
    """
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
    from PySide6.QtCore import Qt

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
    month_lbl.setStyleSheet(_nav_label_style(NAV_LABEL_DEFAULT_COLOR))
    month_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    layout.addWidget(month_lbl)

    if next_btn is not None:
        layout.addWidget(next_btn)

    return container, month_lbl


# Symmetric vertical padding (unscaled px) above and below the nav row, so the
# prev/next buttons and the month/year label sit vertically centred in the tray
# rather than jammed against the top edge of each tab.
NAV_HEADER_V_PADDING = 14
# Left/right inset so an optional trailing button (e.g. Archive Month) does not
# sit flush against the tab edge. Applied symmetrically to keep centring intact.
NAV_HEADER_EDGE_PADDING = 10

# Subtle bordered "tray" around the nav cluster, matching the dark_theme group
# boxes (same colour and corner radius). The border width/radius stay unscaled
# so the tray matches those group boxes at every UI scale; the layout insets
# below are scaled via ui_scale.px like the rest of the nav header.
NAV_TRAY_BORDER_COLOR = "#3a4156"
NAV_TRAY_BORDER_RADIUS_PX = 6
# Inset the tray from the tab edges so its sides line up with the content margin.
NAV_TRAY_EDGE_INSET = 11
# Gap above and below the tray so it floats between the tabs and the content.
NAV_TRAY_FLOAT_MARGIN = 8


def build_centered_nav_header(
    initial_text: str, prev_btn=None, next_btn=None, trailing_widget=None
):
    """Return (QWidget, QLabel): the nav cluster centred within a full-width row.

    The returned widget is meant to be placed OUTSIDE the scroll area (see
    ScrollableTab), so it spans the full tab width and centres identically on
    every tab, unaffected by that tab's scrollbar gutter or content overflow.

    The nav cluster lives inside a bordered "navTray" widget that is inset from
    the tab edges and floats with a gap above and below. The tray pads itself
    symmetrically top and bottom so the cluster stays vertically centred inside
    the border. The cluster is laid out in the centre column of a three-column
    grid whose outer columns carry equal stretch, so it sits at the exact tray
    midpoint on every tab. `trailing_widget`, if given, is placed in the right
    column (so its button aligns vertically with the nav cluster) without moving
    the cluster, since the centre column's position depends only on the equal
    outer-column stretch, not on the trailing widget's width.
    """
    from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout
    from PySide6.QtCore import Qt
    from clear_budget.ui import ui_scale

    nav_center, month_lbl = build_nav_month_widget(
        initial_text, prev_btn=prev_btn, next_btn=next_btn
    )

    # Bordered tray. WA_StyledBackground is required for a plain QWidget to paint
    # a stylesheet border; the #navTray id selector keeps the border off the
    # child widgets.
    tray = QWidget()
    tray.setObjectName("navTray")
    tray.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    tray.setStyleSheet(
        f"#navTray {{ border: 1px solid {NAV_TRAY_BORDER_COLOR};"
        f" border-radius: {NAV_TRAY_BORDER_RADIUS_PX}px; }}"
    )
    # Three-column grid: the outer columns carry equal stretch, so the centre
    # column (the nav cluster) is always positioned at the exact midpoint of the
    # tray regardless of whether a trailing widget is present. This keeps the
    # cluster in the identical horizontal position on every tab; the previous
    # stretch-plus-spacer approach drifted by a pixel or two between the tab
    # with a trailing button and those without it.
    row = QGridLayout(tray)
    edge = ui_scale.px(NAV_HEADER_EDGE_PADDING)
    vpad = ui_scale.px(NAV_HEADER_V_PADDING)
    row.setContentsMargins(edge, vpad, edge, vpad)
    row.setHorizontalSpacing(0)
    row.setColumnStretch(0, 1)
    row.setColumnStretch(1, 0)
    row.setColumnStretch(2, 1)
    align_v = Qt.AlignmentFlag.AlignVCenter
    row.addWidget(nav_center, 0, 1, Qt.AlignmentFlag.AlignHCenter | align_v)
    if trailing_widget is not None:
        # A left balance of equal width keeps both outer columns matched even
        # when space is tight, so the centre column never gets squeezed off
        # the midpoint.
        left_balance = QWidget()
        left_balance.setFixedWidth(trailing_widget.sizeHint().width())
        row.addWidget(left_balance, 0, 0, Qt.AlignmentFlag.AlignLeft | align_v)
        row.addWidget(trailing_widget, 0, 2, Qt.AlignmentFlag.AlignRight | align_v)

    # Full-width header that insets the tray from the tab edges and lets it float
    # with a symmetric gap above and below, keeping the cluster centred in the
    # region between the tabs and the first content line.
    header = QWidget()
    outer = QVBoxLayout(header)
    inset = ui_scale.px(NAV_TRAY_EDGE_INSET)
    floatm = ui_scale.px(NAV_TRAY_FLOAT_MARGIN)
    outer.setContentsMargins(inset, floatm, inset, floatm)
    outer.addWidget(tray)
    return header, month_lbl


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
