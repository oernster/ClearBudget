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
"""

import pytest

from clear_budget.ui.widgets._tab_cursor import NO_CURSOR, next_candidate

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
