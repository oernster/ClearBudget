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
    from clear_budget.shared.resources import find_logo_png_path

    return find_logo_png_path()


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


def build_graph_icon_button(glyph_height: int, on_click):
    """The app icon as a tabbable button that opens the month graph.

    It used to sit in the upper tray beside the month, which put a control
    that ACTS on the application in the row that only says which month is
    being read. It belongs with the tabs it is sized against, so it is built
    here for the lower tray and returns None when the icon cannot be resolved,
    exactly as the decorative version did.

    It takes the TAB run's image scale, not the tray's bare glyph height,
    because it is drawn INSIDE that run, immediately after the Cards tab. The
    three tab pictures are scaled up by `TAB_IMAGE_SCALE` to hold their own
    optically beside the tray's emoji; this one was left at 1.0 from its days
    in the upper tray, so it painted 46 tall against their 62 and its base sat
    8px above theirs. A row of icons that do not share a bottom edge reads as
    badly set rather than as deliberately varied, which is the very effect
    `tab_icons` introduced that constant to cure. Imported inside the function
    to keep the two modules' import order free of each other.
    """
    from clear_budget.ui.utils.tab_icons import TAB_IMAGE_SCALE

    pixmap = _load_cropped_icon_pixmap()
    if pixmap is None:
        return None
    return _build_icon_graph_button(
        pixmap, round(glyph_height * TAB_IMAGE_SCALE), on_click
    )


def build_nav_month_widget(initial_text: str, prev_btn=None, next_btn=None):
    """Return (QWidget, QLabel) - the month cluster for the upper tray.

    If `prev_btn`/`next_btn` are given, they are placed either side of the
    month label so the navigation buttons flank the title.

    The app icon is NOT here any more. It opened the month graph, which acts
    on the application, while this row only says which month is being read;
    it now sits in the lower tray with the tabs it is sized against (see
    `build_graph_icon_button`). Nothing decorative replaced it: a second copy
    of the window icon said nothing the title bar had not; a dead icon in
    a row of live buttons reads as a broken one.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHBoxLayout, QWidget

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    if prev_btn is not None:
        layout.addWidget(prev_btn)

    month_lbl = NavLabel.create(initial_text)
    apply_nav_label_color(month_lbl, NAV_LABEL_DEFAULT_COLOR)
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

# Inset the tray from the tab edges so its sides line up with the content margin.
NAV_TRAY_EDGE_INSET = 11
# Gap above and below the tray so it floats between the tabs and the content.
NAV_TRAY_FLOAT_MARGIN = 8


def _bordered_tray():
    """An empty bordered nav tray, padded and ready for a layout.

    WA_StyledBackground is required for a plain QWidget to paint a stylesheet
    border; the #navTray id selector (styled by the theme QSS) keeps that
    border off the child widgets.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    tray = QWidget()
    tray.setObjectName("navTray")
    tray.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return tray


def _tray_margins():
    """The (edge, vertical) padding every tray uses, at the current UI scale."""
    from clear_budget.ui import ui_scale

    return ui_scale.px(NAV_HEADER_EDGE_PADDING), ui_scale.px(NAV_HEADER_V_PADDING)


def build_centered_nav_header(
    initial_text: str,
    prev_btn=None,
    next_btn=None,
    leading=(),
    tabs=(),
    pre_theme=(),
    trailing=(),
):
    """Return (QWidget, QLabel, theme_btn): the tab's two nav trays.

    TWO trays, stacked, because they answer different questions and one row
    could not hold both without the month being pushed off the middle:

    * TRAY 1, topmost, carries ONLY what is about the month being viewed:
      Previous, the month and year, then Next. Nothing else is in it, so it is centred on the window by its
      own emptiness rather than by balancing anything.
    * TRAY 2 carries everything that acts on the application: the `leading`
      widgets (load, save, Preferences, Bank Account and a separator), then
      the `tabs` (the four primary tabs, which live here rather than in a strip
      of their own), then at the FAR RIGHT the sun/moon toggle (`theme_btn`)
      followed by the `trailing` widgets (How It Works).

    The returned widget is meant to be placed OUTSIDE the scroll area (see
    ScrollableTab), so it spans the full tab width and reads identically on
    every tab, unaffected by that tab's scrollbar gutter or content overflow.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

    from clear_budget.ui import ui_scale

    nav_center, month_lbl = build_nav_month_widget(
        initial_text, prev_btn=prev_btn, next_btn=next_btn
    )
    edge, vpad = _tray_margins()
    align_v = Qt.AlignmentFlag.AlignVCenter

    # TRAY 1: the month cluster, alone. A stretch either side is enough to
    # centre it exactly. It is the whole reason this is now two trays: a
    # single row with the icon run in it could only centre the cluster by
    # reserving that run's width again on the empty side, which does not fit
    # at the window's own width floor. It cost the cluster its characters
    # ("Previous" came out as "Previo"). Give the cluster a row of its own and
    # the arithmetic disappears rather than being balanced.
    month_tray = _bordered_tray()
    month_row = QHBoxLayout(month_tray)
    month_row.setContentsMargins(edge, vpad, edge, vpad)
    month_row.addStretch(1)
    month_row.addWidget(nav_center, 0, align_v)
    month_row.addStretch(1)

    # TRAY 2: the application's controls, left to right, with the toggle and
    # How It Works at the far right where they have always been.
    action_tray = _bordered_tray()
    action_row = QHBoxLayout(action_tray)
    action_row.setContentsMargins(edge, vpad, edge, vpad)
    action_row.setSpacing(8)

    def _place(widgets) -> None:
        """Add each widget in order, skipping any that could not be built.

        `build_graph_icon_button` returns None when the app icon cannot be
        resolved, so that a missing asset costs the tray one control rather
        than the whole window. Without this skip the None reached
        `addWidget` and took the application down at startup instead.
        """
        for widget in widgets:
            if widget is not None:
                action_row.addWidget(widget, 0, align_v)

    _place(leading)
    _place(tabs)
    action_row.addStretch(1)
    # `pre_theme` is the RIGHT-hand group: everything here sits after the
    # stretch, so it is pinned to the right edge beside the toggle rather than
    # running on from the tabs.
    _place(pre_theme)
    theme_btn = _build_theme_toggle_button(nav_glyph_height(prev_btn))
    action_row.addWidget(theme_btn, 0, align_v)
    _place(trailing)

    header = QWidget()
    outer = QVBoxLayout(header)
    inset = ui_scale.px(NAV_TRAY_EDGE_INSET)
    floatm = ui_scale.px(NAV_TRAY_FLOAT_MARGIN)
    outer.setContentsMargins(inset, floatm, inset, floatm)
    outer.setSpacing(floatm)
    outer.addWidget(month_tray)
    outer.addWidget(action_tray)
    return header, month_lbl, theme_btn
