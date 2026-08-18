"""Tests for the MonthGap value object."""

from clear_budget.domain.value_objects.month_gap import MonthGap


def _gap(income: int, bills: int, interest: int = 0) -> MonthGap:
    return MonthGap(
        income_pence=income, bank_bills_pence=bills, card_interest_pence=interest
    )


class TestMonthGap:
    def test_a_month_short_of_its_bills_names_what_it_needs(self):
        gap = _gap(income=182400, bills=249087)
        assert gap.needed_pence == 66687
        assert not gap.holds_flat

    def test_a_month_that_covers_its_bills_holds_flat(self):
        gap = _gap(income=250000, bills=200000)
        assert gap.holds_flat
        assert gap.needed_pence == -50000

    def test_covering_the_bills_exactly_still_holds_flat(self):
        gap = _gap(income=200000, bills=200000)
        assert gap.holds_flat
        assert gap.needed_pence == 0

    def test_card_interest_is_never_folded_into_the_bank_gap(self):
        # Interest accrues on the cards and never leaves the bank account, so
        # it must not move the figure that says what the month needs.
        without = _gap(income=182400, bills=249087, interest=0)
        with_interest = _gap(income=182400, bills=249087, interest=17011)
        assert without.needed_pence == with_interest.needed_pence
        assert with_interest.card_interest_pence == 17011

    def test_str_names_the_state_and_the_interest(self):
        assert "needs 66687" in str(_gap(income=182400, bills=249087, interest=17011))
        assert "card_interest=17011" in str(
            _gap(income=182400, bills=249087, interest=17011)
        )
        assert "holds flat" in str(_gap(income=250000, bills=200000))
