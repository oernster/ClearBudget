"""The worked example on How It Works must be what the code actually returns.

The screen teaches pro-rating with a specific sum: 200.00 of food on the 11th
of a 30-day month leaves a stated amount still due. A reader checks a worked
example against the screen, which is the whole reason it is there, so a figure
that drifts from the function is worse than no example at all.

It had drifted. The screen said 126 where `prorate_remaining_pence` returns
126.66; nothing anywhere would have noticed: the tray and the view strip
each have a structural guard, while the three rules underneath them had none,
which is why that is the half of the page that went stale.

The numbers are READ OUT of the sentence rather than restated here, so
rewriting the example to use different figures does not need this file
edited; it needs the new figures to be right.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py).
"""

from __future__ import annotations

import re
from pathlib import Path

from clear_budget.domain.services._prorating import prorate_remaining_pence

_ROOT = Path(__file__).resolve().parents[2]
_HELP = _ROOT / "clear_budget" / "ui" / "widgets" / "how_it_works_dialog.py"

# The sentence, with every number it commits to captured: the bill, the day it
# is read on, the length of the month and the figure the screen promises.
_EXAMPLE = re.compile(
    r"&pound;([\d,]+(?:\.\d+)?) of food on the (\d+)(?:st|nd|rd|th) of a\s+"
    r"(\d+)-day month leaves &pound;([\d,]+(?:\.\d+)?)",
    re.MULTILINE,
)

_PENCE_PER_UNIT = 100


def _pence(text: str) -> int:
    """A currency figure from the page as pence."""
    return round(float(text.replace(",", "")) * _PENCE_PER_UNIT)


def _example() -> tuple[int, int, int, int]:
    match = _EXAMPLE.search(_HELP.read_text(encoding="utf-8"))
    assert match, (
        "the pro-rating example is not on the How It Works page in the shape "
        "this guard reads. If the wording changed, change the pattern; do not "
        "delete the guard, because the example is what a reader checks."
    )
    amount, day, days, stated = match.groups()
    return _pence(amount), int(day), int(days), _pence(stated)


def test_the_page_states_a_worked_example_to_check() -> None:
    """Guard the guard: a scan that finds nothing proves nothing."""
    amount_pence, day, days_total, stated_pence = _example()
    assert amount_pence > 0
    assert 1 <= day <= days_total
    assert stated_pence > 0


def test_the_stated_figure_is_what_the_prorating_returns() -> None:
    """The number on the screen is the function's own answer, to the penny."""
    amount_pence, day, days_total, stated_pence = _example()
    assert stated_pence == prorate_remaining_pence(amount_pence, day, days_total)
