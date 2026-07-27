"""Qt-free tests for where the tab strip's keyboard cursor lands.

What the cursor promises, and why:

  * it never rests on the tab already showing. Landing there would spend a
    keypress to highlight what the user is looking at, which is the bug this
    cursor exists to fix: after the last menu title, the ring must reach the
    NEXT tab.
  * it wraps at both ends, so the strip is a cycle like the rest of the ring.
  * it skips disabled and hidden tabs, so the ring never stalls on a tab that
    cannot be opened.
  * it terminates. A strip with nothing to move to reports NO_CURSOR rather
    than walking for ever.

Those promises describe the WRAPPING walk, which belongs to Up and Down, the
strip's own keys. Tab and Shift+Tab are the whole window's keys and use the
BOUNDED walk instead: it stops at the end of the strip rather than wrapping, so
the ring can carry on out of the tab bar. Both are tested here.
"""

import pytest

from clear_budget.ui.widgets._tab_cursor import (
    NO_CURSOR,
    next_candidate,
    next_candidate_bounded,
)

# The real strip: Monthly Budget, Solvency, Credit Cards, Archive.
_COUNT = 4
_MONTHLY, _SOLVENCY, _CARDS, _ARCHIVE = range(_COUNT)


def _walk(start, delta, skip=frozenset()):
    return next_candidate(count=_COUNT, start=start, delta=delta, skip=skip)


# The reported bug: after Help, the ring must reach Solvency.
def test_entering_forward_skips_the_tab_already_showing():
    """On Monthly Budget, stepping in forward lands on Solvency."""
    assert _walk(_MONTHLY, 1, skip=frozenset({_MONTHLY})) == _SOLVENCY


def test_entering_backward_lands_on_the_tab_before():
    """Stepping in backward from Monthly Budget wraps round to Archive."""
    assert _walk(_MONTHLY, -1, skip=frozenset({_MONTHLY})) == _ARCHIVE


def test_the_current_tab_is_passed_over_mid_walk():
    """Walking back past the current tab skips it rather than resting on it."""
    assert _walk(_CARDS, -1, skip=frozenset({_SOLVENCY})) == _MONTHLY


@pytest.mark.parametrize(
    ("start", "delta", "expected"),
    [
        (_ARCHIVE, 1, _MONTHLY),
        (_MONTHLY, -1, _ARCHIVE),
    ],
)
def test_the_cursor_wraps_at_both_ends(start, delta, expected):
    """The strip is a cycle, the same as the ring it sits on."""
    assert _walk(start, delta, skip=frozenset()) == expected


def test_a_disabled_or_hidden_tab_is_stepped_over():
    """Skipped tabs are passed, however many of them sit in a row."""
    skip = frozenset({_MONTHLY, _SOLVENCY, _CARDS})
    assert _walk(_MONTHLY, 1, skip=skip) == _ARCHIVE


def test_a_strip_with_nowhere_to_go_reports_no_cursor():
    """One tab, and it is the one showing, so there is no candidate."""
    assert next_candidate(count=1, start=0, delta=1, skip=frozenset({0})) == NO_CURSOR


def test_every_tab_skipped_reports_no_cursor():
    """The walk gives up after a full lap instead of looping."""
    assert _walk(_MONTHLY, 1, skip=frozenset(range(_COUNT))) == NO_CURSOR


def test_an_empty_strip_reports_no_cursor():
    """No tabs at all, so no modulo by zero and no candidate."""
    assert next_candidate(count=0, start=0, delta=1, skip=frozenset()) == NO_CURSOR


# ---- the bounded walk: Tab and Shift+Tab -----------------------------------
#
# The reported bug: on Credit Cards with the cursor on Archive, Shift+Tab left
# the strip entirely and highlighted Help, the last menu title. Every tab is a
# stop on the ring, so it should have reached Solvency, passing over the tab
# already showing.


def _bounded(start, delta, skip=frozenset()):
    return next_candidate_bounded(count=_COUNT, start=start, delta=delta, skip=skip)


def test_stepping_back_from_archive_reaches_solvency():
    """The reported case, with Credit Cards showing."""
    assert _bounded(_ARCHIVE, -1, skip=frozenset({_CARDS})) == _SOLVENCY


def test_stepping_forward_walks_the_strip_left_to_right():
    """Entering forward at the left edge covers every usable tab in order."""
    skip = frozenset({_CARDS})
    first = _bounded(-1, 1, skip=skip)
    second = _bounded(first, 1, skip=skip)
    third = _bounded(second, 1, skip=skip)
    assert [first, second, third] == [_MONTHLY, _SOLVENCY, _ARCHIVE]


def test_stepping_backward_walks_the_strip_right_to_left():
    """And entering backward at the right edge mirrors it."""
    skip = frozenset({_CARDS})
    first = _bounded(_COUNT, -1, skip=skip)
    second = _bounded(first, -1, skip=skip)
    third = _bounded(second, -1, skip=skip)
    assert [first, second, third] == [_ARCHIVE, _SOLVENCY, _MONTHLY]


@pytest.mark.parametrize(
    ("start", "delta"),
    [(_ARCHIVE, 1), (_MONTHLY, -1)],
)
def test_the_end_of_the_strip_reports_no_cursor_rather_than_wrapping(start, delta):
    """This is what hands the ring back out of the tab bar.

    Wrapping here would trap the ring inside the strip: Tab would circle the
    tabs for ever and never reach the content below them.
    """
    assert _bounded(start, delta) == NO_CURSOR


def test_the_tab_already_showing_is_passed_over_mid_walk():
    """Skipped tabs are stepped through, not stopped on."""
    assert _bounded(_MONTHLY, 1, skip=frozenset({_SOLVENCY, _CARDS})) == _ARCHIVE


def test_an_empty_strip_reports_no_cursor_when_bounded_too():
    """No tabs, so no candidate and no arithmetic on an empty range."""
    assert (
        next_candidate_bounded(count=0, start=0, delta=1, skip=frozenset()) == NO_CURSOR
    )
