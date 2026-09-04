"""The shared month/year navigation tray: builders, buttons and sizing.

Everything the tray is made of lives here or in nav_label.py (the month/year
label): the app-icon graph button, the sun/moon theme toggle, the glyph
sizing rules and the two builders every view calls. The public names are
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
    TOGGLE_ICON_SCALE,
    TOGGLE_TARGET_PROPERTY,
    _build_theme_toggle_button,
    apply_toggle_icon,
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


def build_nav_month_widget(initial_text: str, prev_btn=None, next_btn=None):
    """Return (QWidget, QLabel) - the month cluster for the upper tray.

    If `prev_btn`/`next_btn` are given, they are placed either side of the
    month label so the navigation buttons flank the title.

    The app icon is NOT here any more. It opened the month graph, which acts
    on the application, while this row only says which month is being read.
    It moved to the lower tray with the view buttons it was sized against, then
    stopped being an icon button at all: the graph is a VIEW now, so what
    stands there is the Graph button itself. Nothing decorative replaced it in
    this row: a second copy of the window icon said nothing the title bar had
    not; a dead icon in a row of live buttons reads as a broken one.
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
# rather than jammed against the top edge of each view.
NAV_HEADER_V_PADDING = 14
# Left/right inset so an optional trailing button (e.g. Archive Month) does not
# sit flush against the view's edge. Applied symmetrically to keep centring intact.
NAV_HEADER_EDGE_PADDING = 10

# Inset the tray from the view edges so its sides line up with the content margin.
NAV_TRAY_EDGE_INSET = 11
# Gap above and below the tray so it floats between the buttons and the content.
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


# The empty twin of the account label, kept the same width so the month
# cluster stays centred on the window rather than on what is left of the row.
_NAV_USER_MIRROR = "NavUserMirror"


def build_centered_nav_header(
    initial_text: str,
    prev_btn=None,
    next_btn=None,
    leading=(),
    views=(),
    pre_theme=(),
    trailing=(),
):
    """Return (QWidget, QLabel, theme_btn): the view's two nav trays.

    TWO trays, stacked, because they answer different questions and one row
    could not hold both without the month being pushed off the middle:

    * TRAY 1, topmost, carries ONLY what is about the month being viewed:
      Previous, the month and year, then Next. Nothing else is in it, so it
      is centred on the window by its own emptiness rather than by balancing
      anything.
    * TRAY 2 carries everything that acts on the application: the `leading`
      widgets (load, save, Preferences, Bank Account and a separator), then
      the `views` (the primary view buttons, which live here rather than in a strip
      of their own), then at the FAR RIGHT the sun/moon toggle (`theme_btn`)
      followed by the `trailing` widgets (How It Works).

    The returned widget is meant to be placed OUTSIDE the scroll area (see
    ScrollableView), so it spans the full view width and reads identically on
    every view, unaffected by that view's scrollbar gutter or content overflow.
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
    # The signed-in account sits at the far left, with an empty MIRROR of it
    # at the far right. Without that mirror the cluster is no longer centred on
    # the window but on what is left of the row, so it drifts right by half
    # the name's width and every view drifts by a different amount as soon as
    # the names differ in length. The mirror costs a widget and keeps the
    # arithmetic at zero.
    user_lbl, user_mirror = _build_nav_user_pair()
    month_row.addWidget(user_lbl, 0, align_v)
    month_row.addStretch(1)
    month_row.addWidget(nav_center, 0, align_v)
    month_row.addStretch(1)
    month_row.addWidget(user_mirror, 0, align_v)

    # TRAY 2: the application's controls, left to right, with the toggle and
    # How It Works at the far right where they have always been.
    action_tray = _bordered_tray()
    action_row = QHBoxLayout(action_tray)
    action_row.setContentsMargins(edge, vpad, edge, vpad)
    action_row.setSpacing(8)

    def _place(widgets) -> None:
        """Add each widget in order, skipping any that could not be built.

        A builder that cannot resolve its artwork returns None rather than
        a blank, so that a missing asset costs the tray one control rather
        than the whole window. Without this skip the None reached
        `addWidget` and took the application down at startup instead.
        """
        for widget in widgets:
            if widget is not None:
                action_row.addWidget(widget, 0, align_v)

    _place(leading)
    _place(views)
    action_row.addStretch(1)
    # `pre_theme` is the RIGHT-hand group: everything here sits after the
    # stretch, so it is pinned to the right edge beside the toggle rather than
    # running on from the buttons.
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


def _build_nav_user_pair():
    """Return (label, mirror) for the month tray's signed-in-account slot.

    The mirror is a plain empty widget whose width is kept equal to the
    label's, so the month cluster between them stays centred on the window
    rather than on whatever the name leaves behind.
    """
    from PySide6.QtWidgets import QWidget

    from clear_budget.ui import label_roles
    from clear_budget.ui.utils.nav_label import NavUserLabel

    # It carries a real QLabel margin (see NavUserLabel) rather than
    # stylesheet padding, for the same reason the month label does: padding is
    # painted but not reliably counted in a label's size hints, so a tray
    # under width pressure reserves less than the text needs and clips it.
    label = NavUserLabel.create()
    label.setObjectName(label_roles.NAV_USER)
    mirror = QWidget()
    mirror.setObjectName(_NAV_USER_MIRROR)
    return label, mirror


def set_nav_user(header, text: str) -> None:
    """Show `text` as the signed-in account on a view's month tray.

    Set from MainWindow rather than passed into each view's constructor,
    because the views are built from a budget and know nothing about who is
    signed in; this keeps that knowledge in the one place that has it.

    Takes the HEADER, never the view that built it. `ScrollableView` lifts the
    header out of its view so it spans the full view width outside the scroll
    area, which leaves the label no longer a descendant of that view: looking
    for it there finds nothing and silently sets no name at all.

    Does nothing when the header has no such slot, which is what makes it
    safe to call across every view in one loop.
    """
    from PySide6.QtWidgets import QLabel, QWidget

    from clear_budget.ui import label_roles

    label = header.findChild(QLabel, label_roles.NAV_USER)
    if label is None:
        return
    label.set_full_text(text)
    label.ensurePolished()
    parent = label.parentWidget()
    mirror = None if parent is None else parent.findChild(QWidget, _NAV_USER_MIRROR)
    if mirror is not None:
        # Capped at the label's own maximum. Without that cap a long name
        # reserves a mirror wider than the label it mirrors, which shifts the
        # month the other way.
        mirror.setFixedWidth(min(label.sizeHint().width(), label.maximumWidth()))
