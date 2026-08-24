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

# The tray's Bank Account picture, plus the transparent space left below it so
# the artwork sits on the same baseline as the emoji beside it.
_BANK_ICON = "bank-icon.png"
_BANK_ICON_PAD_PX = 2

# The Switch user and Switch budget buttons, supplied pictures rather than
# the emoji they replaced.
_USERS_ICON = "switchuser.png"
_BUDGETS_ICON = "switchbudget.png"
# Load, Save, Preferences and How It Works, likewise. Each is fitted by its
# painted HEIGHT, so the row keeps one baseline whatever the artwork's aspect.
_LOAD_ICON = "opendb.png"
_SAVE_ICON = "savedb.png"
_SETTINGS_ICON = "preferences.png"
_INFO_ICON = "information.png"


def build_save_load_buttons(glyph_height: int) -> tuple[QPushButton, QPushButton]:
    """Return (load_btn, save_btn) for a nav tray, in visual order."""
    load_btn = build_tray_image_button(_LOAD_ICON, "Load database…", glyph_height)
    save_btn = build_tray_image_button(_SAVE_ICON, "Save database", glyph_height)
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
    settings_btn = build_tray_image_button(_SETTINGS_ICON, "Preferences…", glyph_height)
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
    return build_tray_image_button(_INFO_ICON, "How it works", glyph_height)
