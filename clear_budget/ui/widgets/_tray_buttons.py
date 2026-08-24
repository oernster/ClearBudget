"""The navigation tray's buttons, built once and shared by every tab.

Split out of `_save_load_flow`, which held two unrelated concerns: WHAT the
tray's buttons look like, then WHAT the save and load flows do when one is
pressed. Adding the owner challenge to the load flow pushed that module into
the 381 to 399 danger band `tests/structural/test_loc_limits.py` enforces; the two halves had
nothing to say to each other anyway.

Every tab builds the same tray, so these builders are the single definition of
its buttons; the ORDER they are placed in is the tabs' own business and is
pinned by `tests/structural/test_tray_switch_invariants.py`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QPushButton

from clear_budget.ui import label_roles
from clear_budget.ui.utils.icon_buttons import build_tray_image_button
from clear_budget.ui.utils.nav_glyph_size import nav_icon_button_size

# The tray's Bank Account picture, plus the transparent space left below it so
# the artwork sits on the same baseline as the emoji beside it.
_BANK_ICON = "bank-icon.png"
_BANK_ICON_PAD_PX = 2

# The Switch user and Switch budget buttons, supplied pictures rather than
# the emoji they replaced.
_USERS_ICON = "switchuser.png"
_BUDGETS_ICON = "switchbudget.png"


def _tray_icon_button(glyph: str, tooltip: str, glyph_height: int) -> QPushButton:
    """One emoji icon button for the nav tray's far-left group.

    IconAction-styled so it carries the standard three-state ring.

    The glyph is painted once, cropped to its own opaque pixels and set as the
    button's ICON rather than left as button text. Text would be placed by the
    font's em box; every emoji needs a different font size to reach the same
    painted height, so the em boxes differ too. The wide glyphs need the
    largest fonts and sat lowest, two busts finishing 6px below the centre of
    a button where a diskette sat 1px off it. An icon is centred on the
    artwork, so every glyph in the row lands on the same line.

    The size is fixed because Qt's default push-button minimum would otherwise
    make an icon-sized control 80-odd pixels wide; it is taken from what
    THIS glyph paints: the buttons match on height, so a wide glyph is given
    the width it needs rather than being shrunk to fit a narrow one's square.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon

    from clear_budget.ui.utils.glyph_metrics import cropped_glyph_pixmap

    btn = QPushButton()
    btn.setToolTip(tooltip)
    btn.setObjectName(label_roles.ICON_ACTION)
    pixmap = cropped_glyph_pixmap(glyph, glyph_height)
    if pixmap.isNull():
        # No glyph painted (a font without it, a headless font database):
        # the button keeps working as text rather than becoming a blank
        # square, exactly as a tab does when its artwork is missing.
        btn.setText(glyph)
    else:
        btn.setIcon(QIcon(pixmap))
        btn.setIconSize(QSize(pixmap.width(), pixmap.height()))
    btn.setFixedSize(*nav_icon_button_size(glyph, glyph_height))
    return btn


def build_save_load_buttons(glyph_height: int) -> tuple[QPushButton, QPushButton]:
    """Return (load_btn, save_btn) for a nav tray, in visual order."""
    load_btn = _tray_icon_button("📂", "Load database…", glyph_height)
    save_btn = _tray_icon_button("💾", "Save database", glyph_height)
    return load_btn, save_btn


def build_budgets_button(glyph_height: int) -> QPushButton:
    """Return the switch-budget button for a nav tray.

    Sits with load and save, left of the separator, because it acts on the
    application rather than deciding which page is being looked at.
    """
    return build_tray_image_button(_BUDGETS_ICON, "Switch budget…", glyph_height)


def build_users_button(glyph_height: int) -> QPushButton:
    """Return the switch-user button for a nav tray, drawn beside switch-budget.

    It carries SWITCH USER rather than Log Out; the reason is
    reversibility. A tray button is one click with no confirmation; a
    cancelled switch leaves the session exactly as it was, while a mis-clicked
    Log Out would end it. Log Out therefore stays on the Users menu, where
    choosing it is deliberate.
    """
    return build_tray_image_button(_USERS_ICON, "Switch user…", glyph_height)


def build_settings_bank_buttons(
    glyph_height: int,
) -> tuple[QFrame, QPushButton, QPushButton]:
    """Return (separator, settings_btn, bank_btn) for a nav tray.

    The separator is a themed vertical rule, returned here but placed by the
    caller AFTER both buttons: it divides the six controls that act on the
    application (load, save, switch budget, switch user, Preferences, Bank
    Account) from the tabs that follow them, which only decide which page you
    are looking at. It used
    to sit between load/save and the settings pair, back when the tabs were
    a strip of their own and there was nothing else in the tray to divide
    them from.
    """
    separator = QFrame()
    separator.setObjectName(label_roles.SEPARATOR)
    separator.setFrameShape(QFrame.Shape.VLine)
    separator.setFixedHeight(glyph_height)
    settings_btn = _tray_icon_button("⚙️", "Preferences…", glyph_height)
    # A picture rather than the bank emoji, so the one control in this
    # group that is not a glyph. The padding is the reason it needs its own
    # builder: this building has a flat base, so cropped tight and centred
    # it sits lower than the rounded emoji either side of it.
    bank_btn = build_tray_image_button(
        _BANK_ICON, "Bank account", glyph_height, bottom_pad_px=_BANK_ICON_PAD_PX
    )
    return separator, settings_btn, bank_btn


def build_info_button(glyph_height: int) -> QPushButton:
    """Return the How It Works button shown right of the theme toggle.

    Always enabled: the help text changes nothing.
    """
    return _tray_icon_button("ℹ️", "How it works", glyph_height)
