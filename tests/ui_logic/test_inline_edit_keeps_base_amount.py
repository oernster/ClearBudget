"""An inline table edit must not write a month's amount back as the bill's own.

A bill listed for a month on or after a scheduled increase carries that month's
amount in `amount` and its own in `base_amount`. The bill dialog already edits
the latter. The inline table edit did not, so renaming a bill (or changing its
category or due day) while viewing a month after an increase wrote the
increased figure back as the base and restated every earlier month.

Qt-free, in keeping with this package: the rule is a static method taking a
bill and returning a bill.
"""

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.views._month_view_edit_mixin import MonthViewEditMixin

_own_amount = MonthViewEditMixin._own_amount


def _rent(*, amount: Amount, base_amount: Amount | None) -> Bill:
    return Bill(
        id=19,
        name="Rent",
        amount=amount,
        payment_method_id=1,
        category="housing",
        bill_type="fixed",
        day_of_month=1,
        start_ym=YearMonth(2000, 1),
        end_ym=None,
        base_amount=base_amount,
    )


class TestAMonthGovernedByAScheduledChange:
    def test_the_bills_own_amount_is_what_gets_written(self) -> None:
        """September reads 1400; the bill is still worth 1350."""
        listed = _rent(
            amount=Amount.from_pounds(1400), base_amount=Amount.from_pounds(1350)
        )
        assert _own_amount(listed).amount == Amount.from_pounds(1350)

    def test_nothing_else_about_the_bill_moves(self) -> None:
        listed = _rent(
            amount=Amount.from_pounds(1400), base_amount=Amount.from_pounds(1350)
        )
        written = _own_amount(listed)
        assert (written.id, written.name, written.day_of_month) == (19, "Rent", 1)
        assert written.start_ym == YearMonth(2000, 1)


class TestAMonthNoScheduledChangeReaches:
    def test_the_bill_is_handed_back_untouched(self) -> None:
        """No base recorded means the displayed amount IS the bill's own."""
        listed = _rent(amount=Amount.from_pounds(1350), base_amount=None)
        assert _own_amount(listed) is listed
