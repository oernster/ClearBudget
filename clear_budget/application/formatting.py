"""Display formatting for money, percentages and categories. No Qt, no I/O.

Moved out of `ui/utils/format_helpers.py`, which is excluded from the coverage
gate wholesale. That exclusion is right for painting and Qt wiring, but these
are not presentation: turning pence into a figure a person reads is exactly
where a budgeting application gets a number wrong in a way the user believes,
and it was the one part of that file with nothing holding it.

The UI still calls `fmt`; `format_helpers` re-exports it, so no call site moved.

TWO MONEY FORMATS EXIST IN THIS APPLICATION AND THEY DISAGREE. This one is what
the screen shows. `reporting.document.money` is what an exported report shows,
and it groups thousands and puts the sign before the symbol:

    pence      report        screen
    123456     GBP1,234.56   GBP1234.56
    -123456    -GBP1,234.56  GBP-1234.56

Both are pinned by tests so the difference is recorded rather than discovered.
The report's form is the correct one, `GBP-1234.56` being malformed currency,
but the screen's form is what ships today and changing it is a visible change
to every figure in the application, so it is Oliver's call rather than a
silent side effect of moving this code.
"""

from __future__ import annotations

from clear_budget.shared.currency import get_symbol

_PENCE_PER_UNIT = 100
_PERCENT_DECIMALS = 1

# Categories whose stored plural reads wrong as a label for a single item.
_CATEGORY_SINGULARS = {
    "subscriptions": "subscription",
    "utilities": "utility",
}


def fmt(amount: int | float) -> str:
    """Format as a currency string using the active symbol.

    Pass pence as `int` (divided by 100 internally) or pounds as `float` (used
    directly). That overload is a hazard worth stating plainly: `fmt(100)` is
    one pound and `fmt(100.0)` is one hundred, so a caller passing the wrong
    type is silently out by a factor of a hundred with no error anywhere. It is
    preserved exactly as it was because sixty-two call sites depend on it; the
    behaviour is pinned by tests so a change to it cannot be accidental.
    """
    symbol = get_symbol()
    if isinstance(amount, int):
        return f"{symbol}{amount / _PENCE_PER_UNIT:.2f}"
    return f"{symbol}{amount:.2f}"


def percentage(value: float) -> str:
    """Format an already-computed percentage, one decimal place.

    Takes a percentage (75.0 means 75%), not a fraction.
    """
    return f"{value:.{_PERCENT_DECIMALS}f}%"


def format_category(category: str) -> str:
    """Turn a stored category key into a label: underscores out, title case."""
    formatted = _CATEGORY_SINGULARS.get(category, category)
    return formatted.replace("_", " ").title()
