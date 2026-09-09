"""A displayed path breaks at its separators, never mid-name or after `C:`.

The measurement is faked as one unit per character, so the cases read as
widths rather than as font metrics; the real font arrives through `wrap_for`.
"""

from __future__ import annotations

from clear_budget.ui.path_display import wrap_path

_WINDOWS_PATH = r"C:\Users\Oliver\AppData\Local\ClearBudget\clearbudget_backup.db"


def _chars(text: str) -> int:
    return len(text)


def test_short_path_stays_on_one_line() -> None:
    assert wrap_path(r"C:\Temp\b.db", len(r"C:\Temp\b.db"), _chars) == r"C:\Temp\b.db"


def test_breaks_after_a_separator() -> None:
    lines = wrap_path(_WINDOWS_PATH, 30, _chars).split("\n")
    assert all(line.endswith("\\") for line in lines[:-1])
    assert "".join(lines) == _WINDOWS_PATH


def test_every_line_fits_the_width() -> None:
    assert all(
        len(line) <= 30 for line in wrap_path(_WINDOWS_PATH, 30, _chars).split("\n")
    )


def test_drive_is_never_alone_on_its_line() -> None:
    # A line with room for the prefix and nothing beyond it: the width at
    # which the bare `C:` used to appear.
    first = wrap_path(_WINDOWS_PATH, len("C:\\Users\\"), _chars).split("\n")[0]
    assert first == "C:\\Users\\"


def test_unc_prefix_is_never_alone_on_its_line() -> None:
    unc = r"\\nas\share\budget.db"
    first = wrap_path(unc, len("\\\\nas\\"), _chars).split("\n")[0]
    assert first == "\\\\nas\\"


def test_forward_slashes_break_the_same_way() -> None:
    assert wrap_path("/home/oliver/b.db", 8, _chars).split("\n") == [
        "/home/",
        "oliver/",
        "b.db",
    ]


def test_a_segment_too_wide_is_broken_between_characters() -> None:
    # A filename holds no separator; Qt finds no break opportunity in one
    # either, so leaving it whole is what ran it off the edge of the dialog.
    assert wrap_path("C:\\a\\averylongfilename.db", 6, _chars).split("\n") == [
        "C:\\a\\",
        "averyl",
        "ongfil",
        "ename.",
        "db",
    ]


def test_no_line_exceeds_the_width_whatever_the_name() -> None:
    long_name = "C:\\a\\" + "x" * 200
    assert all(len(line) <= 12 for line in wrap_path(long_name, 12, _chars).split("\n"))


def test_empty_text_wraps_to_nothing() -> None:
    assert wrap_path("", 10, _chars) == ""
