"""Tests for the MonthAfloat value object.

The distinction from MonthGap is the whole point of the type, so it is
asserted directly: a month can need a great deal to hold flat while needing
nothing at all to stay afloat.
"""

from clear_budget.domain.value_objects.month_afloat import MonthAfloat
from clear_budget.domain.value_objects.month_gap import MonthGap


def _afloat(low: int, limit: int = 0) -> MonthAfloat:
    return MonthAfloat(low_point_pence=low, overdraft_limit_pence=limit)


class TestNoFacility:
    """With nothing arranged the floor is zero, so any dip is a breach."""

    def test_a_month_that_dips_under_names_what_would_rescue_it(self):
        assert _afloat(low=-26813).needed_pence == 26813

    def test_a_month_that_stays_positive_needs_nothing(self):
        assert _afloat(low=55416).needed_pence == 0

    def test_a_month_that_stays_positive_reports_its_margin(self):
        assert _afloat(low=55416).headroom_pence == 55416

    def test_a_month_that_dips_under_has_no_margin(self):
        assert _afloat(low=-26813).headroom_pence == 0

    def test_landing_on_exactly_zero_still_stays_afloat(self):
        """The floor is a floor, not a cliff edge: touching it is not a breach."""
        touching = _afloat(low=0)
        assert touching.stays_afloat
        assert touching.needed_pence == 0
        assert touching.headroom_pence == 0

    def test_the_floor_with_no_facility_is_zero(self):
        assert _afloat(low=0).floor_pence == 0

    def test_staying_afloat_is_the_sign_of_the_low_point(self):
        assert _afloat(low=1).stays_afloat
        assert not _afloat(low=-1).stays_afloat


class TestAnArrangedOverdraft:
    """Borrowing the bank has agreed to is not a shortfall.

    The account breaches only when it goes past the facility, so the figure
    that keeps the month afloat is measured from the agreed floor.
    """

    def test_dipping_inside_the_facility_needs_nothing(self):
        assert _afloat(low=-26813, limit=50000).needed_pence == 0

    def test_only_the_excess_beyond_the_facility_has_to_be_found(self):
        assert _afloat(low=-109042, limit=50000).needed_pence == 59042

    def test_the_facility_moves_the_floor_down(self):
        assert _afloat(low=0, limit=50000).floor_pence == -50000

    def test_headroom_is_measured_from_the_agreed_floor(self):
        """Room left inside the facility is room, so it is reported as such."""
        assert _afloat(low=-26813, limit=50000).headroom_pence == 23187

    def test_resting_exactly_on_the_limit_still_stays_afloat(self):
        assert _afloat(low=-50000, limit=50000).stays_afloat


class TestAgainstTheHoldFlatGap:
    """Why the type exists: the two figures answer different questions.

    MonthGap knows nothing about the balance a month opens with, so it cannot
    say what would rescue a month. Stating it where a reader expects a rescue
    figure was the defect this type was added to close.
    """

    def test_a_month_can_need_much_to_hold_flat_and_nothing_to_stay_afloat(self):
        """It runs at a heavy loss all month and never once goes under."""
        gap = MonthGap(
            income_pence=122400,
            bank_bills_pence=204629,
            card_interest_pence=0,
        )
        assert gap.needed_pence == 82229
        assert _afloat(low=55416).needed_pence == 0

    def test_the_two_figures_differ_for_the_same_month(self):
        """The month opened with a cushion, so far less rescues it."""
        gap = MonthGap(
            income_pence=122400,
            bank_bills_pence=204629,
            card_interest_pence=0,
        )
        assert _afloat(low=-26813).needed_pence == 26813
        assert gap.needed_pence != _afloat(low=-26813).needed_pence
