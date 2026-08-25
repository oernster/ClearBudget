"""The commitment entity, including the ending rule bills already follow."""

from datetime import date

import pytest

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.recurrence import Recurrence
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.shared.errors import InvalidCommitmentError

AUGUST = YearMonth(year=2026, month=8)


def _commitment(**overrides) -> Commitment:
    fields = {
        "id": 1,
        "name": "Car insurance",
        "amount": Amount(pence=62000),
        "due_date": date(2026, 11, 14),
        "recurrence": Recurrence.annual(),
        "created_month": AUGUST,
    }
    fields.update(overrides)
    return Commitment(**fields)


class TestValidation:
    @pytest.mark.parametrize("name", ["", "   "])
    def test_a_commitment_needs_a_name(self, name):
        with pytest.raises(InvalidCommitmentError):
            _commitment(name=name)

    def test_it_cannot_end_before_it_starts(self):
        with pytest.raises(InvalidCommitmentError):
            _commitment(final_month=YearMonth(year=2026, month=7))

    def test_it_may_end_in_the_month_it_starts(self):
        assert _commitment(final_month=AUGUST).final_month == AUGUST


class TestOutstanding:
    def test_nothing_held_leaves_the_whole_amount(self):
        assert _commitment().outstanding_pence == 62000

    def test_what_is_held_comes_off(self):
        assert _commitment(already_held=Amount(pence=2000)).outstanding_pence == 60000

    def test_over_holding_is_not_a_credit(self):
        """More held than the bill costs is over-holding, never a negative."""
        assert _commitment(already_held=Amount(pence=99999)).outstanding_pence == 0


class TestWhenItApplies:
    def test_an_inactive_commitment_applies_nowhere(self):
        assert not _commitment(active=False).applies_to(AUGUST)

    def test_it_does_not_apply_before_it_was_entered(self):
        assert not _commitment().applies_to(YearMonth(year=2026, month=7))

    def test_it_applies_from_the_month_it_was_entered(self):
        assert _commitment().applies_to(AUGUST)

    def test_it_runs_on_while_it_has_no_final_month(self):
        assert _commitment().applies_to(YearMonth(year=2030, month=1))

    def test_it_applies_through_its_final_month(self):
        ended = _commitment(final_month=YearMonth(year=2026, month=10))
        assert ended.applies_to(YearMonth(year=2026, month=10))

    def test_it_stops_after_its_final_month(self):
        """Ending never erases: the months it really ran in keep it."""
        ended = _commitment(final_month=YearMonth(year=2026, month=10))
        assert not ended.applies_to(YearMonth(year=2026, month=11))

    def test_a_day_is_answered_by_its_month(self):
        assert _commitment().applies_on(date(2026, 8, 31))
        assert not _commitment().applies_on(date(2026, 7, 31))
