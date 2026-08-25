"""The navigation tray's buttons, built once and shared by every view.

Split out of `_save_load_flow`, which held two unrelated concerns: WHAT the
tray's buttons look like, then WHAT the save and load flows do when one is
pressed. Adding the owner challenge to the load flow pushed that module into
the 381 to 399 danger band `tests/structural/test_loc_limits.py` enforces; the two halves had
nothing to say to each other anyway.

Every view builds the same tray, so these builders are the single definition of
its buttons; the ORDER they are placed in is the views' own business and is
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

# The Switch budget button, a supplied picture rather than the emoji it
# replaced.
_BUDGETS_ICON = "switchbudget.png"
# Load, Save and How It Works, likewise. Each is fitted by its
# painted HEIGHT, so the row keeps one baseline whatever the artwork's aspect.
_LOAD_ICON = "opendb.png"
_SAVE_ICON = "savedb.png"
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


def build_bank_button(glyph_height: int) -> tuple[QFrame, QPushButton]:
    """Return (separator, bank_btn) for a nav tray.

    The separator is a themed vertical rule the caller places BEFORE the bank
    button, setting the account's own settings apart from the file shortcuts
    left of it. The settings button that used to stand here went when the
    Preferences content folded into the Bank Account dialog, which this one
    button now opens.
    """
    separator = QFrame()
    separator.setObjectName(label_roles.SEPARATOR)
    separator.setFrameShape(QFrame.Shape.VLine)
    separator.setFixedHeight(glyph_height)
    # A picture rather than the bank emoji. The padding is the reason it
    # needs naming: this building has a flat base, so cropped tight and
    # centred it sits lower than the artwork either side of it.
    bank_btn = build_tray_image_button(
        _BANK_ICON,
        "Bank account and preferences",
        glyph_height,
        bottom_pad_px=_BANK_ICON_PAD_PX,
    )
    return separator, bank_btn


def build_tray_separator(glyph_height: int) -> QFrame:
    """Return a themed vertical rule for a nav tray.

    A second copy of the rule `build_bank_button` returns, for the
    right-hand group: it stands before Archive, dividing the pinned-right
    trio (Archive, theme, help) from the stretch beside them.
    """
    separator = QFrame()
    separator.setObjectName(label_roles.SEPARATOR)
    separator.setFrameShape(QFrame.Shape.VLine)
    separator.setFixedHeight(glyph_height)
    return separator


def build_info_button(glyph_height: int) -> QPushButton:
    """Return the How It Works button shown right of the theme toggle.

    Always enabled: the help text changes nothing.
    """
    return build_tray_image_button(_INFO_ICON, "How it works", glyph_height)
