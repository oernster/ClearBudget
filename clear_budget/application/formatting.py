"""Display formatting for money, percentages and categories. No Qt, no I/O.

Moved out of `ui/utils/format_helpers.py`, which is excluded from the coverage
gate wholesale. That exclusion is right for painting and Qt wiring, but these
are not presentation: turning pence into a figure a person reads is exactly
where a budgeting application gets a number wrong in a way the user believes,
and it was the one part of that file with nothing holding it.

The UI still calls `fmt`; `format_helpers` re-exports it, so no call site moved.

ONE MONEY FORMAT. This module is the single place money is rendered, for the
screen and for an exported report alike; `reporting.document.money` is an alias
onto it. They used to differ, the screen printing `GBP1234.56` and `GBP-1234.56`
where a report printed `GBP1,234.56` and `-GBP1,234.56`, so the same figure read
two ways depending on where you saw it and a negative on screen was malformed
currency, the symbol sitting outside its own minus sign.

`reporting.chart_svg._money` is deliberately NOT this: an axis tick is a bare
grouped number with no symbol and no decimals, which is a different job.
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


def _render(units: float) -> str:
    """Render whole currency units: sign, then symbol, then grouped amount.

    The sign leads. `-GBP5.00` is the readable form; `GBP-5.00` puts the symbol
    outside the number it belongs to and is easy to misread as positive.
    """
    symbol = get_symbol()
    sign = "-" if units < 0 else ""
    return f"{sign}{symbol}{abs(units):,.2f}"


def money_from_pence(pence: int) -> str:
    """Format an integer number of pence."""
    return _render(pence / _PENCE_PER_UNIT)


def money_from_pounds(pounds: float) -> str:
    """Format an amount already expressed in whole currency units."""
    return _render(pounds)


def fmt(amount: int | float) -> str:
    """Format as a currency string using the active symbol.

    Pass pence as `int` or whole units as `float`. That overload is a hazard
    worth stating plainly: `fmt(100)` is one pound and `fmt(100.0)` is one
    hundred, so a caller passing the wrong type is silently out by a factor of
    a hundred with no error anywhere. It is preserved because sixty-two call
    sites depend on it, and pinned by a test so it cannot change by accident.
    Prefer `money_from_pence` in new code, where the unit is in the name.
    """
    if isinstance(amount, int):
        return money_from_pence(amount)
    return money_from_pounds(amount)


def percentage(value: float) -> str:
    """Format an already-computed percentage, one decimal place.

    Takes a percentage (75.0 means 75%), not a fraction.
    """
    return f"{value:.{_PERCENT_DECIMALS}f}%"


def format_category(category: str) -> str:
    """Turn a stored category key into a label: underscores out, title case."""
    formatted = _CATEGORY_SINGULARS.get(category, category)
    return formatted.replace("_", " ").title()
