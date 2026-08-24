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
    qss="""
        QWidget { background: #f4f4f4; color: #1f2937; font-family: 'Segoe UI'; }
        QLabel#HeaderTitle { font-size: 38px; font-weight: 700; }
        QLabel#HeaderVersion { font-size: 14px; color: #6b7280; }
        QLabel#SubTitle { font-size: 22px; font-weight: 700; color: #374151; }
        QLabel#StatusLine { font-size: 13px; color: #6b7280; }

        QCheckBox { spacing: 10px; font-size: 13px; }
        QCheckBox::indicator { width: 16px; height: 16px; }

        QPushButton#ThemeToggle {
            background: #5b7799; color: white; border: none;
            padding: 0px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#ThemeToggle:hover { background: #4f6885; }

        QPushButton#LicenceButton {
            background: #5b7799; color: white; border: none;
            padding: 10px 18px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#LicenceButton:hover { background: #4f6885; }

        QPushButton#PrimaryAction {
            background: #5b7799; color: white; border: none;
            padding: 14px 26px; border-radius: 26px; font-size: 14px;
            font-weight: 700; min-width: 150px;
        }
        QPushButton#PrimaryAction:hover { background: #4f6885; }

        QPushButton#DangerAction {
            background: #7a1f25; color: white; border: none;
            padding: 12px 26px; border-radius: 22px; font-size: 13px;
            font-weight: 700; min-width: 190px;
        }
        QPushButton#DangerAction:hover { background: #6a1b21; }

        QLineEdit {
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 10px;
            padding: 8px;
        }
        QPushButton#BrowseButton {
            background: #e5e7eb;
            border: none;
            border-radius: 10px;
            padding: 8px 12px;
        }
        QPushButton#BrowseButton:hover { background: #dbe0e8; }

        QProgressBar#ProgressBar {
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 10px;
            height: 16px;
            text-align: center;
        }
        QProgressBar#ProgressBar::chunk {
            background: #6b89ab;
            border-radius: 8px;
            width: 10px;
            margin: 1px;
        }
    """,
)


DARK = Theme(
    name="dark",
    toggle_glyph=toggle_glyph(THEME_DARK),
    toggle_tooltip=toggle_tooltip(THEME_DARK),
    qss="""
        QWidget { background: #161827; color: #e5e7eb; font-family: 'Segoe UI'; }
        QLabel#HeaderTitle { font-size: 38px; font-weight: 700; color: #a3a8c9; }
        QLabel#HeaderVersion { font-size: 14px; color: #9ca3af; }
        QLabel#SubTitle { font-size: 22px; font-weight: 700; color: #a3a8c9; }
        QLabel#StatusLine { font-size: 13px; color: #cbd5e1; }

        QCheckBox { spacing: 10px; font-size: 13px; }
        QCheckBox::indicator { width: 16px; height: 16px; }

        QPushButton#ThemeToggle {
            background: #5b7799; color: white; border: none;
            padding: 0px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#ThemeToggle:hover { background: #4f6885; }

        QPushButton#LicenceButton {
            background: #5b7799; color: white; border: none;
            padding: 10px 18px; border-radius: 18px; font-weight: 600;
        }
        QPushButton#LicenceButton:hover { background: #4f6885; }

        QPushButton#PrimaryAction {
            background: #5b7799; color: white; border: none;
            padding: 14px 26px; border-radius: 26px; font-size: 14px;
            font-weight: 700; min-width: 150px;
        }
        QPushButton#PrimaryAction:hover { background: #4f6885; }

        QPushButton#DangerAction {
            background: #7a1f25; color: white; border: none;
            padding: 12px 26px; border-radius: 22px; font-size: 13px;
            font-weight: 700; min-width: 190px;
        }
        QPushButton#DangerAction:hover { background: #6a1b21; }

        QLineEdit {
            background: #0f1220;
            border: 1px solid #2b2f44;
            border-radius: 10px;
            padding: 8px;
        }
        QPushButton#BrowseButton {
            background: #24283b;
            border: none;
            border-radius: 10px;
            padding: 8px 12px;
            color: #e5e7eb;
        }
        QPushButton#BrowseButton:hover { background: #2b3050; }

        QProgressBar#ProgressBar {
            background: #0f1220;
            border: 1px solid #2b2f44;
            border-radius: 10px;
            height: 16px;
            text-align: center;
        }
        QProgressBar#ProgressBar::chunk {
            background: #6b89ab;
            border-radius: 8px;
            width: 10px;
            margin: 1px;
        }
    """,
)
