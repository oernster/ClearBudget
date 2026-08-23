"""The content card below the (hidden) tab bar.

This module used to carry the tab strip itself: pill geometry, a hover rule, a
selected rule and a long note about the keyboard cursor painted on exactly
that pill. All of it went when the four tabs moved into the navigation tray as
ordinary icon buttons and Qt's own bar was hidden. A stylesheet for a widget
nobody can see is not styling, it is a description of a former design.

What survives is the one rule that is still drawn: the pane, which is the card
the tab CONTENT sits on. The three-state ring and the current-tab mark for the
buttons that replaced the strip live in `_theme_controls` with the rest of the
tray, under `QPushButton#NavTabButton`.

Pure string building, no Qt. `build_qss` as a whole is NOT callable without a
QApplication, since it resolves the system font and generates the spin-box
arrow images, so keeping these rules in a function of their own is what lets
them be tested (see `tests/ui_logic/test_highlight_text_colour.py`).
"""

from __future__ import annotations

# Inset of the tab strip from the left edge. The strip is hidden; the pane
# below it is not, so Qt still lays the two out together.
TAB_BAR_LEFT_INSET_PX = 4


def tab_qss(t: dict[str, str]) -> str:
    """Return the stylesheet for the card the tab content sits on."""
    return f"""
/* The content below the tabs is one card. The bar itself is hidden (the tabs
   are buttons in the navigation tray), so it carries no rules of its own
   beyond suppressing the chrome Qt would otherwise draw for it. */
QTabWidget::pane {{
    border: 1px solid {t["border"]};
    border-radius: 8px;
    background-color: {t["panel_bg"]};
}}

QTabWidget::tab-bar {{
    left: {TAB_BAR_LEFT_INSET_PX}px;
}}

QTabBar {{
    background: transparent;
    border: none;
}}
"""
