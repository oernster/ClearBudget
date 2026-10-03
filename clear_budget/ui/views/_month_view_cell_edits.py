"""What a typed table cell turns a bill or an income into. No Qt.

The bill and income tables used to parse their cells differently: the bill
amount through the shared reader, the income amount with `float()` after
stripping the symbol (so "£1,500" as the app prints it was silently put
back); both due days went through a bare `int()`, so -3 or 45 were saved. Both
tables now read through the same two rules the dialogs use: `pence_from_text`
and `due_day_from_text`. Each raises with a message the view shows.

Kept apart from the mixin so the rules can be tested without a QApplication.
"""

import dataclasses

from clear_budget.application.formatting import pence_from_text
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.due_day import due_day_from_text

# What each table prints in the day column for "no fixed day". Reading it
# back means no day rather than a refusal.
BILL_NO_DAY_MARK = "N/A"
INCOME_NO_DAY_MARK = "~"

BILL_NAME_COL = 0
BILL_AMOUNT_COL = 1
BILL_CATEGORY_COL = 2
BILL_DAY_COL = 4

INCOME_NAME_COL = 0
INCOME_AMOUNT_COL = 1
INCOME_DAY_COL = 3


def _amount(text: str) -> Amount:
    return Amount(pence=pence_from_text(text))


def edited_bill(bill, col: int, text: str):
    """The bill with column `col` set from `text`; None for a column not edited.

    Raises InvalidAmountError or InvalidDueDayError, each carrying a message
    fit to show, when the text cannot be saved.
    """
    if col == BILL_NAME_COL:
        return dataclasses.replace(bill, name=text or bill.name)
    if col == BILL_AMOUNT_COL:
        return dataclasses.replace(bill, amount=_amount(text))
    if col == BILL_CATEGORY_COL:
        return dataclasses.replace(bill, category=text.lower().replace(" ", "_"))
    if col == BILL_DAY_COL:
        day = due_day_from_text(text, no_day_mark=BILL_NO_DAY_MARK)
        return dataclasses.replace(bill, day_of_month=day)
    return None


def edited_income(income, col: int, text: str):
    """The income with column `col` set from `text`; None for a column not edited.

    Raises as `edited_bill` does.
    """
    if col == INCOME_NAME_COL:
        return dataclasses.replace(income, name=text or income.name)
    if col == INCOME_AMOUNT_COL:
        return dataclasses.replace(income, amount=_amount(text))
    if col == INCOME_DAY_COL:
        day = due_day_from_text(text, no_day_mark=INCOME_NO_DAY_MARK)
        return dataclasses.replace(income, day_of_month=day)
    return None
