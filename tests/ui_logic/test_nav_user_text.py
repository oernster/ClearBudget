"""What the month tray says about who is signed in.

The account moved out of the title bar, so this string is now the only place
the application names the person whose budget is on screen. On a shared
machine that is the one thing worth being certain of, which is why the text
is pinned rather than left to a format string nobody reads.
"""

from __future__ import annotations

from clear_budget.ui.utils.nav_header import nav_user_text


def test_an_ordinary_account_shows_just_its_name() -> None:
    assert nav_user_text("oliver", read_only=False) == "oliver"


def test_a_read_only_viewer_is_told_so() -> None:
    """The title bar no longer carries it, so this must."""
    assert nav_user_text("guest", read_only=True) == "guest (Read-only)"


def test_the_name_is_never_altered() -> None:
    """Whatever the account is called is what is shown, verbatim."""
    for name in ("ab", "john doe", "Bartholomew-Fitzwilliam", "  spaced  "):
        assert nav_user_text(name, read_only=False) == name
        assert nav_user_text(name, read_only=True).startswith(name)
