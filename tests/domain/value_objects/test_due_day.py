"""A due day is 1 to 31 or no day at all, wherever it is entered.

The Bill dialog limited the day with its spin box. The table cell parsed with
a bare `int()` and the entity checked nothing. A day of -3 drew its drop on
the 28th, made the month walk report a low on "day -3" and was never deducted
overnight; 45 was reported as day 45.
"""

import pytest

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.due_day import (
    FIRST_DUE_DAY,
    LAST_DUE_DAY,
    check_due_day,
    due_day_from_storage,
    due_day_from_text,
)
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.shared.errors import InvalidDueDayError

_OUT_OF_RANGE = [-3, 0, 32, 45]


def _bill(day) -> Bill:
    return Bill(
        id=1,
        name="Rent",
        amount=Amount(pence=100),
        payment_method_id=1,
        category="housing",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
    )


def _income(day) -> IncomeSource:
    return IncomeSource(
        id=1, name="Pay", amount=Amount(pence=100), is_reliable=True, day_of_month=day
    )


class TestTheRange:
    def test_the_range_is_every_day_any_month_can_have(self) -> None:
        assert (FIRST_DUE_DAY, LAST_DUE_DAY) == (1, 31)

    @pytest.mark.parametrize("day", [None, 1, 15, 28, 31])
    def test_in_range_and_no_day_are_accepted(self, day) -> None:
        check_due_day(day)

    @pytest.mark.parametrize("day", _OUT_OF_RANGE)
    def test_out_of_range_is_refused(self, day) -> None:
        with pytest.raises(InvalidDueDayError):
            check_due_day(day)

    def test_a_flag_is_not_a_day(self) -> None:
        """`True` is an int in Python; as a day it is a mistake, not the 1st."""
        with pytest.raises(InvalidDueDayError):
            check_due_day(True)


class TestTheEntitiesRefuseIt:
    @pytest.mark.parametrize("day", _OUT_OF_RANGE)
    def test_a_bill(self, day) -> None:
        with pytest.raises(InvalidDueDayError):
            _bill(day)

    @pytest.mark.parametrize("day", _OUT_OF_RANGE)
    def test_an_income(self, day) -> None:
        with pytest.raises(InvalidDueDayError):
            _income(day)

    def test_valid_days_still_build(self) -> None:
        assert _bill(31).day_of_month == 31
        assert _income(None).day_of_month is None


class TestWhatIsTypedIntoTheCell:
    @pytest.mark.parametrize(
        ("typed", "day"), [("1", 1), (" 31 ", 31), ("7", 7), ("", None), ("  ", None)]
    )
    def test_a_day_or_nothing_is_read(self, typed: str, day) -> None:
        assert due_day_from_text(typed) == day

    def test_the_tables_own_no_day_mark_reads_as_no_day(self) -> None:
        assert due_day_from_text("N/A", no_day_mark="N/A") is None
        assert due_day_from_text("~", no_day_mark="~") is None

    @pytest.mark.parametrize("typed", ["-3", "0", "32", "45", "abc", "1.5", "~"])
    def test_anything_else_is_refused_with_a_message(self, typed: str) -> None:
        with pytest.raises(InvalidDueDayError) as caught:
            due_day_from_text(typed)
        assert "1 to 31" in str(caught.value)


class TestADayAlreadyStored:
    """Rows written before the rule must still load rather than crash a view.

    Each is read the way the overnight update already treated it: a day past
    the end of the month fell due on the month's last day; a day below 1 was
    never applied, which is what "no fixed day" means.
    """

    @pytest.mark.parametrize(("raw", "day"), [(None, None), (1, 1), (31, 31)])
    def test_good_values_pass_through(self, raw, day) -> None:
        assert due_day_from_storage(raw) == day

    @pytest.mark.parametrize("raw", [32, 45])
    def test_past_the_longest_month_reads_as_its_last_day(self, raw) -> None:
        assert due_day_from_storage(raw) == LAST_DUE_DAY

    @pytest.mark.parametrize("raw", [0, -3])
    def test_below_the_first_reads_as_no_day(self, raw) -> None:
        assert due_day_from_storage(raw) is None
