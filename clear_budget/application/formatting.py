"""Display formatting for money, percentages and categories. No Qt, no I/O.

Moved out of `ui/utils/format_helpers.py`, which is excluded from the coverage
gate wholesale. That exclusion is right for painting and Qt wiring; these are
not presentation: turning pence into a figure a person reads is exactly where
a budgeting application gets a number wrong in a way the user believes. It was
the one part of that file with nothing holding it.

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

from decimal import Decimal, InvalidOperation

from clear_budget.domain.value_objects.amount import MAX_AMOUNT_PENCE
from clear_budget.shared.currency import get_symbol
from clear_budget.shared.errors import InvalidAmountError

_PENNY_PLACES = 2
_PENCE_PER_UNIT = 10**_PENNY_PLACES
_MAX_UNITS = Decimal(MAX_AMOUNT_PENCE).scaleb(-_PENNY_PLACES)
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
    sites depend on it; a test pins it so it cannot change by accident.
    Prefer `money_from_pence` in new code, where the unit is in the name.
    """
    if isinstance(amount, int):
        return money_from_pence(amount)
    return money_from_pounds(amount)


def pence_from_text(text: str, *, signed: bool = False) -> int:
    """Read a typed amount into exact integer pence, never through a float.

    The inverse of `_render`; it has to live beside it: what the application
    prints is what a person types back. `_render` groups thousands and leads
    with the sign, so the sign, the symbol, the grouping separators and
    surrounding space are all accepted.

    Raises InvalidAmountError, carrying a message fit to show the user, for
    an empty entry, anything that is not a finite number, an amount finer
    than a penny and an amount whose size is above MAX_AMOUNT_PENCE. A
    negative amount is refused too unless `signed` (a bank balance, which
    is negative when overdrawn). A fraction of a penny is refused rather
    than rounded: every rounding rule stores a figure the user did not type.
    """
    typed = text.strip()
    if not typed:
        raise InvalidAmountError("Enter an amount.")
    not_an_amount = InvalidAmountError(f"'{typed}' is not an amount.")
    negative = typed.startswith("-")
    cleaned = typed[1:].lstrip() if negative else typed
    symbol = get_symbol()
    if cleaned.startswith(symbol):
        # Sliced by length, never `lstrip`, which takes a character SET: a
        # multi-character symbol such as "A$" would eat any leading A or $.
        cleaned = cleaned[len(symbol) :]
    cleaned = cleaned.replace(",", "").replace(" ", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise not_an_amount from None
    if not value.is_finite():
        raise not_an_amount
    if value.is_zero():
        return 0
    if negative and value.is_signed():
        raise not_an_amount
    is_negative = negative or value.is_signed()
    if is_negative and not signed:
        raise InvalidAmountError("An amount cannot be negative.")
    # `copy_abs`, compared and never computed with: both are exact, while
    # arithmetic goes through the decimal context and can overflow.
    size = value.copy_abs()
    if size > _MAX_UNITS:
        raise InvalidAmountError(
            f"An amount cannot be more than {money_from_pence(MAX_AMOUNT_PENCE)}."
        )
    pence = _exact_pence(size)
    return -pence if is_negative else pence


def _exact_pence(value: Decimal) -> int:
    """`value` (finite, positive, within the cap) as integer pence.

    Worked on the decimal digits directly so no context precision can round
    anything: the digits shifted past the penny must all be zero.
    """
    _sign, digits, exponent = value.as_tuple()
    shift = exponent + _PENNY_PLACES
    if shift >= 0:
        return int("".join(map(str, digits))) * 10**shift
    kept, dropped = digits[:shift], digits[shift:]
    if any(dropped):
        raise InvalidAmountError(
            "Amounts go to the penny: use at most two decimal places."
        )
    return int("".join(map(str, kept)) or "0")


def percentage(value: float) -> str:
    """Format an already-computed percentage, one decimal place.

    Takes a percentage (75.0 means 75%), not a fraction.
    """
    return f"{value:.{_PERCENT_DECIMALS}f}%"


def format_category(category: str) -> str:
    """Turn a stored category key into a label: underscores out, title case."""
    formatted = _CATEGORY_SINGULARS.get(category, category)
    return formatted.replace("_", " ").title()
