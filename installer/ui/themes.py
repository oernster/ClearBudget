"""Light and dark themes (QSS) for the installer UI.

ONE accent hue family, deliberately muted. The palette used to run three
fully saturated colours from three unrelated hue families at once: a sky
blue button (100% saturation), a hot magenta progress bar (100%) and a
violet heading (92%). Side by side they competed rather than agreed; the
blue also failed its own label, since white text on #7fb0ff measures 2.20:1,
well under the 4.5:1 needed to be read comfortably.

So every accent now sits in the same blue family at roughly a quarter
saturation, differing by lightness rather than by hue; each one is chosen
against a measured contrast rather than by eye. The button fill carries its
white label at 4.62:1, the progress chunk reads against both backgrounds and
the dark heading improved from 6.46:1 to 7.54:1 on the way past.

The danger red is untouched. It is already muted (59.5% saturation, dark)
and it is the one control that SHOULD stand apart from the accent family,
since standing apart is its whole job.
"""

from __future__ import annotations

from dataclasses import dataclass

# The sun and the moon come FROM the application, never a second copy of
# them. See installer.ui._theme_toggle for why the installer borrows its
# toggle face rather than declaring one.
from string import Template

from clear_budget.shared import palette
from clear_budget.ui.theme import toggle_glyph, toggle_tooltip
from clear_budget.ui.theme_tokens import THEME_DARK, THEME_LIGHT


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    toggle_glyph: str
    toggle_tooltip: str
    qss: str


LIGHT = Theme(
    name="light",
    toggle_glyph=toggle_glyph(THEME_LIGHT),
    toggle_tooltip=toggle_tooltip(THEME_LIGHT),
    qss=Template("""
        QWidget { background: $GREY_96; color: $MUTED_BLUE_17; font-family: 'Segoe UI'; }
        QLabel#HeaderTitle { font-size: 38px; font-weight: 700; }
        QLabel#HeaderVersion { font-size: 14px; color: $GREY_46; }
        QLabel#SubTitle { font-size: 22px; font-weight: 700; color: $MUTED_BLUE_27_H217; }
        QLabel#StatusLine { font-size: 13px; color: $GREY_46; }

        QCheckBox { spacing: 10px; font-size: 13px; }
        QCheckBox::indicator { width: 16px; height: 16px; }

        QPushButton#ThemeToggle {
            background: $MUTED_BLUE_48; color: white; border: none;
            padding: 0px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#ThemeToggle:hover { background: $MUTED_BLUE_42; }

        QPushButton#LicenceButton {
            background: $MUTED_BLUE_48; color: white; border: none;
            padding: 10px 18px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#LicenceButton:hover { background: $MUTED_BLUE_42; }

        QPushButton#PrimaryAction {
            background: $MUTED_BLUE_48; color: white; border: none;
            padding: 14px 26px; border-radius: 26px; font-size: 14px;
            font-weight: 700; min-width: 150px;
        }
        QPushButton#PrimaryAction:hover { background: $MUTED_BLUE_42; }

        QPushButton#DangerAction {
            background: $RED_30; color: white; border: none;
            padding: 12px 26px; border-radius: 22px; font-size: 13px;
            font-weight: 700; min-width: 190px;
        }
        QPushButton#DangerAction:hover { background: $RED_26; }

        QLineEdit {
            background: white;
            border: 1px solid $GREY_84;
            border-radius: 10px;
            padding: 8px;
        }
        QPushButton#BrowseButton {
            background: $GREY_91;
            border: none;
            border-radius: 10px;
            padding: 8px 12px;
        }
        QPushButton#BrowseButton:hover { background: $MUTED_BLUE_88; }

        QProgressBar#ProgressBar {
            background: white;
            border: 1px solid $GREY_84;
            border-radius: 10px;
            height: 16px;
            text-align: center;
        }
        QProgressBar#ProgressBar::chunk {
            background: $MUTED_BLUE_55;
            border-radius: 8px;
            width: 10px;
            margin: 1px;
        }
    """).substitute(vars(palette)),
)


DARK = Theme(
    name="dark",
    toggle_glyph=toggle_glyph(THEME_DARK),
    toggle_tooltip=toggle_tooltip(THEME_DARK),
    qss=Template("""
        QWidget { background: $MUTED_INDIGO_12; color: $GREY_91; font-family: 'Segoe UI'; }
        QLabel#HeaderTitle { font-size: 38px; font-weight: 700; color: $MUTED_INDIGO_71; }
        QLabel#HeaderVersion { font-size: 14px; color: $GREY_65; }
        QLabel#SubTitle { font-size: 22px; font-weight: 700; color: $MUTED_INDIGO_71; }
        QLabel#StatusLine { font-size: 13px; color: $MUTED_BLUE_84; }

        QCheckBox { spacing: 10px; font-size: 13px; }
        QCheckBox::indicator { width: 16px; height: 16px; }

        QPushButton#ThemeToggle {
            background: $MUTED_BLUE_48; color: white; border: none;
            padding: 0px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#ThemeToggle:hover { background: $MUTED_BLUE_42; }

        QPushButton#LicenceButton {
            background: $MUTED_BLUE_48; color: white; border: none;
            padding: 10px 18px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#LicenceButton:hover { background: $MUTED_BLUE_42; }

        QPushButton#PrimaryAction {
            background: $MUTED_BLUE_48; color: white; border: none;
            padding: 14px 26px; border-radius: 26px; font-size: 14px;
            font-weight: 700; min-width: 150px;
        }
        QPushButton#PrimaryAction:hover { background: $MUTED_BLUE_42; }

        QPushButton#DangerAction {
            background: $RED_30; color: white; border: none;
            padding: 12px 26px; border-radius: 22px; font-size: 13px;
            font-weight: 700; min-width: 190px;
        }
        QPushButton#DangerAction:hover { background: $RED_26; }

        QLineEdit {
            background: $MUTED_INDIGO_09;
            border: 1px solid $MUTED_INDIGO_22;
            border-radius: 10px;
            padding: 8px;
        }
        QPushButton#BrowseButton {
            background: $MUTED_INDIGO_19;
            border: none;
            border-radius: 10px;
            padding: 8px 12px;
            color: $GREY_91;
        }
        QPushButton#BrowseButton:hover { background: $MUTED_INDIGO_24; }

        QProgressBar#ProgressBar {
            background: $MUTED_INDIGO_09;
            border: 1px solid $MUTED_INDIGO_22;
            border-radius: 10px;
            height: 16px;
            text-align: center;
        }
        QProgressBar#ProgressBar::chunk {
            background: $MUTED_BLUE_55;
            border-radius: 8px;
            width: 10px;
            margin: 1px;
        }
    """).substitute(vars(palette)),
)
