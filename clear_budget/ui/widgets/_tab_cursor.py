"""Cursor walking for the tab strip's keyboard cursor. Pure Python, no Qt.

The rules that decide where the cursor lands (wrap at both ends, never rest
on a tab that is skipped) live here rather than in the widget, so they can be
tested without a QApplication in tests/ui_logic/test_tab_cursor.py, the same
way the month graph's curve maths is.
"""

from __future__ import annotations

NO_CURSOR = -1


def next_candidate(*, count: int, start: int, delta: int, skip: frozenset[int]) -> int:
    """The first index from `start` in `delta`'s direction that is not skipped.

    Wraps at both ends and gives up after one full lap, so a strip whose only
    usable tab is the one already showing reports NO_CURSOR rather than
    looping for ever.

    Args:
        count: How many tabs the strip has.
        start: The index to walk from; it is never itself returned.
        delta: +1 to walk forward, -1 to walk back.
        skip: Indices the cursor may not rest on (the current tab, plus any
            disabled or hidden one).
    """
    if count <= 0:
        return NO_CURSOR
    for step in range(1, count + 1):
        index = (start + delta * step) % count
        if index not in skip:
            return index
    return NO_CURSOR
