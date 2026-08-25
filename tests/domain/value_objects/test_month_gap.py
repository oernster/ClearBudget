"""Tests for the MonthGap value object."""

from clear_budget.domain.value_objects.month_gap import MonthGap


def _gap(income: int, bills: int, interest: int = 0, reserve: int = 0) -> MonthGap:
    return MonthGap(
        income_pence=income,
        bank_bills_pence=bills,
        card_interest_pence=interest,
        reserve_pence=reserve,
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


class TestTheReserve:
    """A month has to find what it sets aside, exactly as it finds a bill.

    The contrast with card interest is the whole point: interest accrues on
    the cards and never leaves the bank, so it stays out of the gap; a reserve
    leaves the same account the bills do, so it goes in.
    """

    def test_setting_aside_makes_a_month_need_more(self):
        without = _gap(income=200000, bills=180000)
        with_reserve = _gap(income=200000, bills=180000, reserve=30000)
        assert without.needed_pence == -20000
        assert with_reserve.needed_pence == 10000

    def test_a_month_that_cannot_fund_its_reserve_does_not_hold_flat(self):
        """It pays every bill and still borrows from a future month."""
        gap = _gap(income=200000, bills=180000, reserve=30000)
        assert not gap.holds_flat

    def test_a_month_that_funds_both_holds_flat(self):
        assert _gap(income=250000, bills=180000, reserve=30000).holds_flat

    def test_setting_nothing_aside_leaves_the_figure_untouched(self):
        """Every budget that does not use the Reserves page reads as before."""
        assert _gap(income=182400, bills=249087).needed_pence == 66687
