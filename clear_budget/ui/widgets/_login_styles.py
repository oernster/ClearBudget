"""Shared styling for the sign-in screen and the dialogs that match it.

Split out of login_dialog.py to keep that module under the 400-line limit
(enforced by tests/structural/test_loc_limits.py) once the username dropdown
arrived. Four dialogs draw the same fields, so the styling they share lives
here rather than being reached for through one of them.

Every rule is resolved when the dialog is BUILT, so a dialog opened after a
theme switch follows the theme now in force.
"""

from clear_budget.ui import ui_scale


def link_style() -> str:
    """The flat text-link buttons on the sign-in screen."""
    from PySide6.QtWidgets import QApplication

    from clear_budget.ui import theme
    from clear_budget.ui.theme_tokens import tokens_for

    t = tokens_for(theme.current_theme(QApplication.instance()))
    return ui_scale.style(
        f"QPushButton {{ color: {t['link']}; font-size: 12px;"
        " border: none; background: transparent; padding: 0; margin: 0; }"
        f"QPushButton:hover {{ color: {t['link_hover']};"
        " text-decoration: underline; }"
    )


def input_style() -> str:
    from PySide6.QtWidgets import QApplication

    from clear_budget.ui import theme
    from clear_budget.ui.theme_tokens import tokens_for

    t = tokens_for(theme.current_theme(QApplication.instance()))
    return ui_scale.style(
        "QLineEdit {"
        f"  background-color: {t['input_bg']};"
        f"  color: {t['input_text']};"
        f"  border: 1px solid {t['separator']};"
        "  border-radius: 4px;"
        "  padding: 6px 8px;"
        "  font-size: 14px;"
        "}"
        "QLineEdit:focus {"
        f"  border-color: {t['info']};"
        "}"
    )


def combo_style() -> str:
    """The username dropdown, styled to match the plain field it replaces.

    The COMBO carries the box: its background, border, radius and padding,
    with the inner line edit flattened to transparent so the two do not
    each draw one. Both are given the same font size explicitly, since an
    unstyled inner edit falls back to a POINT-sized font that renders
    taller than the box the combo gives it and clips the name.

    The arrow is left to the platform and NOTHING here touches ::drop-down,
    which is the whole reason one is visible: styling that subcontrol at all
    stops the native chevron being painted, which is how every dropdown in
    the app came to have no arrow at all. Drawing a replacement from CSS
    borders was tried too and rendered as a small white block, since Qt
    paints ::down-arrow as an image subcontrol rather than a box.
    """
    from PySide6.QtWidgets import QApplication

    from clear_budget.ui import theme
    from clear_budget.ui.theme_tokens import tokens_for

    t = tokens_for(theme.current_theme(QApplication.instance()))
    return ui_scale.style(
        "QComboBox {"
        f"  background-color: {t['input_bg']};"
        f"  color: {t['input_text']};"
        f"  border: 1px solid {t['separator']};"
        "  border-radius: 4px;"
        "  padding: 6px 8px;"
        "  font-size: 14px;"
        "}"
        "QComboBox:focus {"
        f"  border-color: {t['info']};"
        "}"
        "QComboBox QLineEdit {"
        "  background: transparent;"
        "  border: none;"
        "  padding: 0;"
        f"  color: {t['input_text']};"
        "  font-size: 14px;"
        "}"
    )
