"""Light and dark themes (QSS) for the installer UI.

THE APPLICATION'S OWN COLOURS, BY ROLE. The installer takes `theme_tokens.DARK`
and `theme_tokens.LIGHT` straight from the app and asks them for a role, the
same way every app surface does: the window is `window_bg`, an action button is
`primary_bg` carrying `primary_text`, Uninstall is `danger_btn_bg`, the heading
is `info`, the one the sign-in screen already paints "ClearBudget" with.

It named its own colours before this, from the same palette module but chosen
separately, so the result was a program that did not look like the thing it
was installing: a navy window against the app's near-black, a dusty steel-blue
button against the app's indigo, a grey-blue heading against the app's cyan.
Two palettes drawn from one palette file still make two palettes. Now there is
one; a change to a token moves both surfaces together.

The GEOMETRY is untouched: every size, radius, padding and weight below is the
one it already had, because a setup program is a short sequence of big
decisions rather than a dense working surface and it is built to be read at
arm's length. Only the source of the colours changed.

Measured after the swap, foreground against background (WCAG AA wants 4.5:1 for
body text): dark theme, body text 15.97:1, muted text 7.79:1, heading 11.17:1,
button label on its fill 5.67:1 and 4.95:1 hovered, Uninstall label 10.02:1;
light theme, body text 16.12:1, heading 5.39:1, button label 5.67:1, Uninstall
label 10.24:1 on the muted red it keeps (see `_LIGHT_OVERRIDES`). One pair
sits under the bar: light-theme muted text at 4.39:1,
which is the value it already had here (`#6b7280` on `#f4f4f4` before, on
`#f3f4f6` now) and the pairing the app itself uses for every muted line it
draws. It moves when the app's token moves, which is the point.

The previous note recorded why the old palette existed: three fully saturated
colours from unrelated hue families, a sky-blue button whose white label
measured 2.20:1, replaced by one muted blue family. That fix is what the app's
own tokens now carry, so the installer no longer needs its own version of it.
"""

from __future__ import annotations

from dataclasses import dataclass

# The sun and the moon come FROM the application, never a second copy of
# them: the same two PICTURES the app's tray wears. See
# installer.ui._theme_toggle for why the installer borrows its toggle face
# rather than declaring one.
from string import Template

from clear_budget.shared import palette
from clear_budget.ui.theme import toggle_icon, toggle_tooltip
from clear_budget.ui.theme_tokens import DARK as APP_DARK
from clear_budget.ui.theme_tokens import LIGHT as APP_LIGHT
from clear_budget.ui.theme_tokens import THEME_DARK, THEME_LIGHT


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    toggle_icon: str
    toggle_tooltip: str
    qss: str


# One sheet for both themes. The installer asks for ROLES, so the only thing
# that differs between light and dark is which token dictionary fills them in,
# exactly as the app's own stylesheet works.
_QSS = Template("""
    QWidget { background: $window_bg; color: $text; font-family: 'Segoe UI'; }
    QLabel#HeaderTitle { font-size: 38px; font-weight: 700; color: $info; }
    QLabel#HeaderVersion { font-size: 14px; color: $text_muted; }
    QLabel#SubTitle { font-size: 22px; font-weight: 700; color: $info; }
    QLabel#StatusLine { font-size: 13px; color: $text_muted; }

    QCheckBox { spacing: 10px; font-size: 13px; }
    QCheckBox::indicator { width: 16px; height: 16px; }

    QPushButton#ThemeToggle {
        background: $primary_bg; color: $primary_text; border: none;
        padding: 0px; border-radius: 18px; font-weight: 600;
    }
    QPushButton#ThemeToggle:hover { background: $primary_hover; }

    QPushButton#LicenceButton {
        background: $primary_bg; color: $primary_text; border: none;
        padding: 10px 18px; border-radius: 18px; font-weight: 600;
    }
    QPushButton#LicenceButton:hover { background: $primary_hover; }

    QPushButton#PrimaryAction {
        background: $primary_bg; color: $primary_text; border: none;
        padding: 14px 26px; border-radius: 26px; font-size: 14px;
        font-weight: 700; min-width: 150px;
    }
    QPushButton#PrimaryAction:hover { background: $primary_hover; }

    QPushButton#DangerAction {
        background: $danger_btn_bg; color: $primary_text; border: none;
        padding: 12px 26px; border-radius: 22px; font-size: 13px;
        font-weight: 700; min-width: 190px;
    }
    QPushButton#DangerAction:hover { background: $danger_btn_hover; }

    QLineEdit {
        background: $input_bg;
        color: $input_text;
        border: 1px solid $border;
        border-radius: 10px;
        padding: 8px;
    }
    QPushButton#BrowseButton {
        background: $panel_bg;
        border: none;
        border-radius: 10px;
        padding: 8px 12px;
        color: $text;
    }
    QPushButton#BrowseButton:hover { background: $hover_fill; }

    QProgressBar#ProgressBar {
        background: $inset_bg;
        border: 1px solid $border;
        border-radius: 10px;
        height: 16px;
        text-align: center;
    }
    QProgressBar#ProgressBar::chunk {
        background: $accent;
        border-radius: 8px;
        width: 10px;
        margin: 1px;
    }
""")


# The one role the setup program keeps its own value for, by decision. The
# app's light danger button is a bright red, which is right inside a budget
# where deleting an account is a rare, deliberate act among quiet controls. It
# is wrong on a page whose whole content is three buttons: there it becomes the
# loudest thing on screen and reads as a warning about the page rather than a
# label on one button. The muted red is the one this window already wore; it
# carries its white label at 10.24:1 against 4.83:1 for the bright one.
_LIGHT_OVERRIDES = {
    "danger_btn_bg": palette.RED_30,
    "danger_btn_hover": palette.RED_26,
}


LIGHT = Theme(
    name="light",
    toggle_icon=toggle_icon(THEME_LIGHT),
    toggle_tooltip=toggle_tooltip(THEME_LIGHT),
    qss=_QSS.substitute({**APP_LIGHT, **_LIGHT_OVERRIDES}),
)


DARK = Theme(
    name="dark",
    toggle_icon=toggle_icon(THEME_DARK),
    toggle_tooltip=toggle_tooltip(THEME_DARK),
    qss=_QSS.substitute(APP_DARK),
)
