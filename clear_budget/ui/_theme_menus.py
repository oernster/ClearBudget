"""Menu bar and menu styling, parameterised by theme tokens.

Split from theme_qss to keep each module under the 400-LOC limit.

Both surfaces follow the app-wide highlight rule: the ring is GREEN and the
text inside it is TEAL, the same accent the selected tab shows. Green text in a
green ring made a highlighted item read as a second kind of selection.
"""

from __future__ import annotations


def menu_qss(t: dict[str, str]) -> str:
    """Return the stylesheet for the menu bar and its menus."""
    return f"""
QMenuBar {{
    background-color: {t["window_bg"]};
    color: {t["text"]};
    border-bottom: 1px solid {t["border"]};
}}

QMenuBar::item {{
    background: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    border: 2px solid {t["ring"]};
    border-radius: 4px;
    color: {t["accent"]};
}}

QMenuBar::item:pressed {{
    background-color: {t["border"]};
    border: 2px solid {t["ring"]};
    border-radius: 4px;
}}

QMenu {{
    background-color: {t["panel_bg"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 4px;
    padding: 4px 0px;
}}

QMenu::item {{
    padding: 6px 24px 6px 12px;
    border: 2px solid transparent;
    border-radius: 3px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    border: 2px solid {t["ring"]};
    color: {t["accent"]};
    background-color: transparent;
}}

QMenu::separator {{
    height: 1px;
    background-color: {t["border"]};
    margin: 4px 8px;
}}
"""
