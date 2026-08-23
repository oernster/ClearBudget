"""The shared month/year navigation tray: builders, buttons and sizing.

Everything the tray is made of lives here or in nav_label.py (the month/year
label): the app-icon graph button, the sun/moon theme toggle, the glyph
sizing rules and the two builders every tab calls. The public names are
re-exported by format_helpers, where the sixty-odd call sites already import
them.
"""

from pathlib import Path

from clear_budget.ui.utils.nav_glyph_size import (  # noqa: F401 (re-exported)
    FALLBACK_ICON_PX as _FALLBACK_ICON_PX,
    NAV_GLYPH_SCALE,
    NAV_ICON_BTN_CHROME_PX,
    nav_glyph_height,
)
from clear_budget.ui.utils.nav_toggle import (  # noqa: F401 (re-exported names)
    TOGGLE_GLYPH_SCALE,
    TOGGLE_TARGET_PROPERTY,
    _build_theme_toggle_button,
    apply_toggle_glyph,
)

from clear_budget.ui.utils.nav_label import (  # noqa: F401 (re-exported names)
    NAV_LABEL_DEFAULT_COLOR,
    NAV_LABEL_MARGIN_PX,
    NavLabel,
    apply_nav_label_color,
)


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


def _load_cropped_icon_pixmap():
    """Return the app icon pixmap cropped to its opaque bounding box or None."""
    global _ICON_PIXMAP_CACHE, _ICON_LOAD_ATTEMPTED
    if _ICON_LOAD_ATTEMPTED:
        return _ICON_PIXMAP_CACHE
    _ICON_LOAD_ATTEMPTED = True

    from PySide6.QtGui import QImage, QPixmap

    from clear_budget.ui.utils.glyph_metrics import opaque_bounding_rect

    if _APP_ICON_PATH is None:
        return None
    image = QImage(str(_APP_ICON_PATH))
    if image.isNull():
        return None
    cropped = image.copy(opaque_bounding_rect(image))
    _ICON_PIXMAP_CACHE = QPixmap.fromImage(cropped)
    return _ICON_PIXMAP_CACHE


def _build_icon_graph_button(icon_pixmap, icon_height, on_click):
    """Return the nav icon as a tabbable QPushButton wired to `on_click`.

    Object-name styled, so it carries its own three-state ring rules: no ring
    at rest, green ring on hover or keyboard focus while enabled, red ring
    while disabled (the app-wide QSS rules do not reach object-name buttons).
    """
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QPushButton

    btn = QPushButton()
    btn.setObjectName("NavGraphButton")
    scaled = icon_pixmap.scaledToHeight(
        icon_height, Qt.TransformationMode.SmoothTransformation
    )
    btn.setIcon(QIcon(scaled))
    btn.setIconSize(QSize(scaled.width(), scaled.height()))
    btn.setToolTip("Show this month as a graph")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(on_click)
    return btn


def build_nav_month_widget(
    initial_text: str, prev_btn=None, next_btn=None, icon_action=None
):
    """Return (QWidget, QLabel, icon_btn) - centered icon + month label for nav.

    If `prev_btn`/`next_btn` are given, they are placed either side of the
    month label so the navigation buttons flank the title. When `icon_action`
    is given the icon becomes a tabbable button wired to it (the month-graph
    opener); otherwise it stays a decorative label and icon_btn is None.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    if prev_btn is not None:
        layout.addWidget(prev_btn)

    icon_height = nav_glyph_height(prev_btn)
    icon_btn = None
    icon_pixmap = _load_cropped_icon_pixmap()
    if icon_pixmap is not None:
        if icon_action is not None:
            icon_btn = _build_icon_graph_button(icon_pixmap, icon_height, icon_action)
            layout.addSpacing(10)
            layout.addWidget(icon_btn)
        else:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(
                icon_pixmap.scaledToHeight(
                    icon_height, Qt.TransformationMode.SmoothTransformation
                )
            )
            # Match the month label's own margin, so the gap before the icon
            # equals the gap after the year (before the next/prev buttons).
            icon_lbl.setContentsMargins(NAV_LABEL_MARGIN_PX, 0, 0, 0)
            layout.addWidget(icon_lbl)

    month_lbl = NavLabel.create(initial_text)
    apply_nav_label_color(month_lbl, NAV_LABEL_DEFAULT_COLOR)
    month_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    layout.addWidget(month_lbl)

    if next_btn is not None:
        layout.addWidget(next_btn)

    return container, month_lbl, icon_btn


# Symmetric vertical padding (unscaled px) above and below the nav row, so the
# prev/next buttons and the month/year label sit vertically centred in the tray
# rather than jammed against the top edge of each tab.
NAV_HEADER_V_PADDING = 14
# Left/right inset so an optional trailing button (e.g. Archive Month) does not
# sit flush against the tab edge. Applied symmetrically to keep centring intact.
NAV_HEADER_EDGE_PADDING = 10

# Inset the tray from the tab edges so its sides line up with the content margin.
NAV_TRAY_EDGE_INSET = 11
# Gap above and below the tray so it floats between the tabs and the content.
NAV_TRAY_FLOAT_MARGIN = 8


def build_centered_nav_header(
    initial_text: str,
    prev_btn=None,
    next_btn=None,
    icon_action=None,
    leading=(),
    trailing=(),
):
    """Return (QWidget, QLabel, icon_btn, theme_btn): the centred nav cluster.

    `icon_action`, when given, turns the tray icon into a tabbable month-graph
    button wired to it; icon_btn is then that button (else None).

    EVERY icon button sits in one run at the tray's FAR LEFT, in this order:
    the `leading` widgets (the load/save pair, then the settings shortcuts),
    then the sun/moon toggle (`theme_btn`), then the `trailing` widgets (How
    It Works). They used to be split, four on the left and two on the right,
    with the month cluster between them. Two groups of the same KIND of
    control, divided by something that is not one of them, reads as two
    different kinds of control; a user hunting for the theme toggle had no
    reason to look at the opposite end of the tray from every other button.
    One run, one place to look. The centre is left to the one cluster that is
    genuinely about the month being viewed.

    The returned widget is meant to be placed OUTSIDE the scroll area (see
    ScrollableTab), so it spans the full tab width and centres identically on
    every tab, unaffected by that tab's scrollbar gutter or content overflow.

    The nav cluster lives inside a bordered "navTray" widget that is inset from
    the tab edges and floats with a gap above and below. The tray pads itself
    symmetrically top and bottom so the cluster stays vertically centred inside
    the border. The cluster is laid out in the centre column of a three-column
    grid whose outer columns carry equal stretch, so it sits at the exact tray
    midpoint on every tab. The outer cells are placed in the side columns (so
    their buttons align vertically with the nav cluster) without moving the
    cluster, since the centre column's position depends only on the equal
    outer-column stretch, not on either cell's width.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QGridLayout,
        QHBoxLayout,
        QSizePolicy,
        QSpacerItem,
        QVBoxLayout,
        QWidget,
    )

    from clear_budget.ui import ui_scale

    nav_center, month_lbl, icon_btn = build_nav_month_widget(
        initial_text, prev_btn=prev_btn, next_btn=next_btn, icon_action=icon_action
    )

    # Bordered tray. WA_StyledBackground is required for a plain QWidget to paint
    # a stylesheet border; the #navTray id selector (styled by the theme QSS)
    # keeps the border off the child widgets.
    tray = QWidget()
    tray.setObjectName("navTray")
    tray.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
    # Left column: every icon button, in one run at the tray's far left.
    left_cell = QWidget()
    left_layout = QHBoxLayout(left_cell)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(8)
    for widget in leading:
        left_layout.addWidget(widget)
    theme_btn = _build_theme_toggle_button(nav_glyph_height(prev_btn))
    left_layout.addWidget(theme_btn)
    for widget in trailing:
        left_layout.addWidget(widget)
    left_layout.addStretch(1)
    row.addWidget(left_cell, 0, 0, Qt.AlignmentFlag.AlignLeft | align_v)
    # Right column: deliberately EMPTY. Deliberately still here too: the centre
    # column sits at the tray's exact midpoint only because the two outer
    # columns carry equal stretch AND matching width; drop this cell and the
    # month cluster drifts left by half the icon run on every tab.
    right_cell = QWidget()
    right_layout = QHBoxLayout(right_cell)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(8)
    right_layout.addStretch(1)
    row.addWidget(right_cell, 0, 2, Qt.AlignmentFlag.AlignRight | align_v)
    # That matching width is a PREFERENCE, never a minimum. The difference is
    # the whole of this block. Every icon button now sits on the left, so a
    # hard minimum reserves the width of the entire run twice over: once for
    # the buttons and once for the empty mirror that centres them. Two runs
    # plus the month cluster do not fit at the window's own width floor;
    # what gave way was the cluster: "Previous" came out as "Previo" and the
    # year lost its last digits, which is the one thing the tray must never
    # shed (`nav_label` pins its own width for the same reason).
    #
    # A spacer that PREFERS the balancing width but may shrink to nothing puts
    # the two demands in the right order: with room the mirror holds and the
    # cluster is centred on the tray; when space runs out the mirror
    # collapses first, so the cluster keeps its size and slides right rather
    # than shedding characters. Nothing is ever clipped to buy symmetry.
    balance_w = left_cell.sizeHint().width()
    right_layout.addSpacerItem(
        QSpacerItem(
            balance_w,
            0,
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Minimum,
        )
    )
    # Full-width header that insets the tray from the tab edges and lets it float
    # with a symmetric gap above and below, keeping the cluster centred in the
    # region between the tabs and the first content line.
    header = QWidget()
    outer = QVBoxLayout(header)
    inset = ui_scale.px(NAV_TRAY_EDGE_INSET)
    floatm = ui_scale.px(NAV_TRAY_FLOAT_MARGIN)
    outer.setContentsMargins(inset, floatm, inset, floatm)
    outer.addWidget(tray)
    return header, month_lbl, icon_btn, theme_btn
