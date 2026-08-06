"""The forward-only rule: a change to a bill never restates history."""

import pytest

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.services.bill_amount_schedule import (
    effective_bill_amount_pence,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.bill_amount_change import BillAmountChange
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.shared.errors import InvalidBillAmountChangeError

_ORIGINAL_RENT = 90_000
_INCREASED_RENT = 100_000
_INCREASED_AGAIN = 110_000


def _rent(*changes: BillAmountChange) -> Bill:
    return Bill(
        id=1,
        name="Rent",
        amount=Amount(pence=_ORIGINAL_RENT),
        payment_method_id=1,
        category="housing",
        bill_type="fixed",
        day_of_month=1,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
        amount_changes=changes,
    )


def _change(year: int, month: int, pence: int) -> BillAmountChange:
    return BillAmountChange(
        effective_year=year, effective_month=month, new_amount=Amount(pence=pence)
    )


class TestEffectiveAmount:
    def test_a_bill_with_no_changes_keeps_its_own_amount(self) -> None:
        assert (
            effective_bill_amount_pence(bill=_rent(), year=2026, month=8)
            == _ORIGINAL_RENT
        )

    def test_the_month_a_change_takes_effect_uses_the_new_amount(self) -> None:
        bill = _rent(_change(2026, 9, _INCREASED_RENT))
        assert (
            effective_bill_amount_pence(bill=bill, year=2026, month=9)
            == _INCREASED_RENT
        )

    def test_every_later_month_uses_the_new_amount(self) -> None:
        bill = _rent(_change(2026, 9, _INCREASED_RENT))
        assert (
            effective_bill_amount_pence(bill=bill, year=2027, month=3)
            == _INCREASED_RENT
        )

    def test_an_earlier_month_keeps_what_it_actually_cost(self) -> None:
        """The rule, stated as a test. History is never restated."""
        bill = _rent(_change(2026, 9, _INCREASED_RENT))
        assert (
            effective_bill_amount_pence(bill=bill, year=2026, month=8) == _ORIGINAL_RENT
        )

    def test_a_month_in_an_earlier_year_is_also_untouched(self) -> None:
        bill = _rent(_change(2026, 1, _INCREASED_RENT))
        assert (
            effective_bill_amount_pence(bill=bill, year=2025, month=12)
            == _ORIGINAL_RENT
        )

    def test_the_latest_applicable_change_wins(self) -> None:
        bill = _rent(
            _change(2026, 9, _INCREASED_RENT),
            _change(2027, 4, _INCREASED_AGAIN),
        )
        assert (
            effective_bill_amount_pence(bill=bill, year=2027, month=6)
            == _INCREASED_AGAIN
        )

    def test_a_month_between_two_changes_uses_the_earlier_one(self) -> None:
        bill = _rent(
            _change(2026, 9, _INCREASED_RENT),
            _change(2027, 4, _INCREASED_AGAIN),
        )
        assert (
            effective_bill_amount_pence(bill=bill, year=2027, month=3)
            == _INCREASED_RENT
        )

    def test_the_order_changes_are_supplied_in_does_not_matter(self) -> None:
        ascending = _rent(
            _change(2026, 9, _INCREASED_RENT), _change(2027, 4, _INCREASED_AGAIN)
        )
        descending = _rent(
            _change(2027, 4, _INCREASED_AGAIN), _change(2026, 9, _INCREASED_RENT)
        )
        for year, month in ((2026, 8), (2026, 9), (2027, 3), (2027, 4)):
            assert effective_bill_amount_pence(
                bill=ascending, year=year, month=month
            ) == effective_bill_amount_pence(bill=descending, year=year, month=month)


class TestChangeValidation:
    def test_a_month_outside_the_calendar_is_rejected(self) -> None:
        with pytest.raises(InvalidBillAmountChangeError):
            _change(2026, 13, _INCREASED_RENT)

    def test_a_zero_month_is_rejected(self) -> None:
        with pytest.raises(InvalidBillAmountChangeError):
            _change(2026, 0, _INCREASED_RENT)

    def test_the_sort_key_orders_by_year_then_month(self) -> None:
        assert _change(2026, 9, 1).sort_key < _change(2027, 1, 1).sort_key
        assert _change(2026, 9, 1).sort_key < _change(2026, 10, 1).sort_key
