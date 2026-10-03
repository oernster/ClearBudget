"""What a typed bill or income table cell saves; what it refuses.

The bill day cell parsed with a bare `int()`, so -3 and 45 were saved; the
income amount cell used `float()` after stripping the symbol, so "£1,500" was
silently put back while the bill cell accepted it. Both tables now read
through the dialogs' own rules; a refusal carries a message to show.

Qt-free, in keeping with this package.
"""

import pytest

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.shared.errors import InvalidAmountError, InvalidDueDayError
from clear_budget.ui.views._month_view_cell_edits import (
    BILL_AMOUNT_COL,
    BILL_CATEGORY_COL,
    BILL_DAY_COL,
    BILL_NAME_COL,
    BILL_NO_DAY_MARK,
    INCOME_AMOUNT_COL,
    INCOME_DAY_COL,
    INCOME_NAME_COL,
    INCOME_NO_DAY_MARK,
    edited_bill,
    edited_income,
)

_BILL = Bill(
    id=1,
    name="Rent",
    amount=Amount(pence=100),
    payment_method_id=1,
    category="housing",
    bill_type="fixed",
    day_of_month=1,
    start_ym=YearMonth(2026, 1),
    end_ym=None,
)
_INCOME = IncomeSource(
    id=1, name="Pay", amount=Amount(pence=100), is_reliable=True, day_of_month=1
)
_UNEDITABLE_COL = 9


class TestTheDayCell:
    @pytest.mark.parametrize("typed", ["-3", "0", "32", "45", "abc"])
    def test_a_bill_day_out_of_range_is_refused(self, typed: str) -> None:
        with pytest.raises(InvalidDueDayError):
            edited_bill(_BILL, BILL_DAY_COL, typed)

    @pytest.mark.parametrize("typed", ["-3", "0", "45", "abc"])
    def test_an_income_day_out_of_range_is_refused(self, typed: str) -> None:
        """It used to keep 45 and clear the day for anything not all digits."""
        with pytest.raises(InvalidDueDayError):
            edited_income(_INCOME, INCOME_DAY_COL, typed)

    def test_a_day_in_range_is_saved(self) -> None:
        assert edited_bill(_BILL, BILL_DAY_COL, "31").day_of_month == 31
        assert edited_income(_INCOME, INCOME_DAY_COL, "15").day_of_month == 15

    def test_empty_or_the_tables_own_mark_means_no_day(self) -> None:
        assert edited_bill(_BILL, BILL_DAY_COL, "").day_of_month is None
        assert edited_bill(_BILL, BILL_DAY_COL, BILL_NO_DAY_MARK).day_of_month is None
        income = edited_income(_INCOME, INCOME_DAY_COL, INCOME_NO_DAY_MARK)
        assert income.day_of_month is None


class TestTheAmountCell:
    @pytest.mark.parametrize("typed", ["£1,500", "1,500", "1500.00"])
    def test_both_tables_read_what_the_app_prints(self, typed: str) -> None:
        assert edited_bill(_BILL, BILL_AMOUNT_COL, typed).amount.pence == 150000
        assert edited_income(_INCOME, INCOME_AMOUNT_COL, typed).amount.pence == 150000

    @pytest.mark.parametrize("typed", ["0.125", "nan", "inf", "-5", "1e19", ""])
    def test_both_tables_refuse_what_cannot_be_saved_exactly(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError):
            edited_bill(_BILL, BILL_AMOUNT_COL, typed)
        with pytest.raises(InvalidAmountError):
            edited_income(_INCOME, INCOME_AMOUNT_COL, typed)


class TestTheOtherCells:
    def test_a_name_and_a_category(self) -> None:
        assert edited_bill(_BILL, BILL_NAME_COL, "Lodging").name == "Lodging"
        assert edited_bill(_BILL, BILL_NAME_COL, "").name == "Rent"
        cat = edited_bill(_BILL, BILL_CATEGORY_COL, "Credit Payment").category
        assert cat == "credit_payment"
        assert edited_income(_INCOME, INCOME_NAME_COL, "Wage").name == "Wage"
        assert edited_income(_INCOME, INCOME_NAME_COL, "").name == "Pay"

    def test_a_column_that_is_not_edited_answers_none(self) -> None:
        assert edited_bill(_BILL, _UNEDITABLE_COL, "x") is None
        assert edited_income(_INCOME, _UNEDITABLE_COL, "x") is None
