"""Whether a scheduled change reaches the month being listed.

Holding a change is not the same as being governed by one. A bill with an
increase effective from September is, in August, still worth exactly what it
says it is worth; the listing has to say so: a base amount recorded for a
month no change reaches tells the UI the amount is not directly editable when
it plainly is.
"""

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.services.bill_amount_schedule import (
    effective_bill_amount_pence,
    scheduled_change_applies,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.bill_amount_change import BillAmountChange
from clear_budget.domain.value_objects.year_month import YearMonth

_SEPTEMBER_INCREASE = BillAmountChange(
    effective_year=2026, effective_month=9, new_amount=Amount.from_pounds(1400)
)


def _rent(*changes: BillAmountChange) -> Bill:
    return Bill(
        id=19,
        name="Rent",
        amount=Amount.from_pounds(1350),
        payment_method_id=1,
        category="housing",
        bill_type="fixed",
        day_of_month=1,
        start_ym=YearMonth(2000, 1),
        end_ym=None,
        amount_changes=changes,
    )


class TestAMonthTheChangeDoesNotReach:
    def test_august_is_not_governed_by_a_september_increase(self) -> None:
        assert not scheduled_change_applies(
            bill=_rent(_SEPTEMBER_INCREASE), year=2026, month=8
        )

    def test_an_earlier_year_is_not_governed_either(self) -> None:
        assert not scheduled_change_applies(
            bill=_rent(_SEPTEMBER_INCREASE), year=2025, month=12
        )

    def test_a_bill_with_no_changes_is_never_governed(self) -> None:
        assert not scheduled_change_applies(bill=_rent(), year=2026, month=9)

    def test_the_amount_is_the_bills_own(self) -> None:
        bill = _rent(_SEPTEMBER_INCREASE)
        assert effective_bill_amount_pence(bill=bill, year=2026, month=8) == 135000


class TestAMonthTheChangeDoesReach:
    def test_the_month_it_starts_in(self) -> None:
        assert scheduled_change_applies(
            bill=_rent(_SEPTEMBER_INCREASE), year=2026, month=9
        )

    def test_every_month_after_it(self) -> None:
        bill = _rent(_SEPTEMBER_INCREASE)
        assert scheduled_change_applies(bill=bill, year=2026, month=12)
        assert scheduled_change_applies(bill=bill, year=2027, month=1)

    def test_the_amount_comes_from_the_schedule(self) -> None:
        bill = _rent(_SEPTEMBER_INCREASE)
        assert effective_bill_amount_pence(bill=bill, year=2026, month=9) == 140000
