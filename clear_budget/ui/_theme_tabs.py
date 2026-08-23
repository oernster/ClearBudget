"""Tab strip styling and pill geometry, parameterised by theme tokens.

Split from theme_qss to keep each module under the 400-LOC limit, and because
the geometry constants here are imported by `NavTabBar`, which paints its
keyboard cursor on exactly this shape: naming them once is what stops the ring
drifting away from the pill it outlines.

Pure string building, no Qt. `build_qss` as a whole is NOT callable without a
QApplication, since it resolves the system font and generates the spin-box
arrow images, so keeping these rules in a function of their own is what lets
the app-wide highlight rule be tested (see
`tests/ui_logic/test_highlight_text_colour.py`).
"""

from __future__ import annotations

# Inset of the tab strip from the left edge, so the first pill lines up with
# the content card below it rather than sitting flush against the window edge.
TAB_BAR_LEFT_INSET_PX = 4

# Tab pill geometry. NavTabBar paints its keyboard cursor on exactly this
# shape, so the numbers are named here once and imported there rather than
# written twice and left to drift.
TAB_MARGIN_RIGHT_PX = 6
TAB_MARGIN_BOTTOM_PX = 6
TAB_BORDER_PX = 2
TAB_RADIUS_PX = 8


def tab_qss(t: dict[str, str]) -> str:
    """Return the stylesheet for the tab strip and the card below it."""
    return f"""
/* Tabs are rounded pills on the window background, with the content below
   them as one card. Unselected pills stay quiet (transparent, no border) so
   only the selected pill and whatever the pointer or keyboard is on carry a
   border; that keeps the three-state ring model intact and drops the boxed
   look of hard-edged tabs butted together. */
QTabWidget::pane {{
    border: 1px solid {t["border"]};
    border-radius: 8px;
    background-color: {t["panel_bg"]};
}}

QTabWidget::tab-bar {{
    left: {TAB_BAR_LEFT_INSET_PX}px;
}}

/* The bar's base line is suppressed on the widget (setDrawBase(False) in
   MainWindow); Qt ignores drawBase set through a stylesheet. */
QTabBar {{
    background: transparent;
    border: none;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {t["text_muted"]};
    padding: 9px 14px;
    margin-right: {TAB_MARGIN_RIGHT_PX}px;
    margin-bottom: {TAB_MARGIN_BOTTOM_PX}px;
    border: {TAB_BORDER_PX}px solid transparent;
    border-radius: {TAB_RADIUS_PX}px;
    font-weight: 600;
}}

/* Highlight text is TEAL, never green. The ring is the green thing; the words
   inside it read as the accent, the same colour the selected tab shows, so the
   strip has one text colour for "this one is live" and one border colour for
   "the pointer or the keyboard is here". Text in the ring's own green made a
   hovered tab look like a second, slightly different selection. The rule holds
   everywhere a green ring goes round text: the menu bar and menu items in
   `_theme_menus` follow it too. */
QTabBar::tab:!selected:hover {{
    background-color: {t["panel_bg"]};
    color: {t["accent"]};
    border-color: {t["ring"]};
}}

QTabBar::tab:selected {{
    background-color: {t["panel_bg"]};
    color: {t["accent"]};
    border-color: {t["accent"]};
}}

/* No focus rule on the selected pill. The bar's keyboard cursor is a separate
   thing from its selection (NavTabBar), and the cursor paints the green ring
   itself on whichever tab it sits on; ringing the selected tab as well would
   put two green rings on the strip. The accent stays a selection colour. */
"""
