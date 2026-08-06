"""What the amount-change entry row does with what is typed into it.

Two defects sit behind these, both found against real data where a rent
increase and an electricity increase were entered and neither reached
September. One of the two was never written to the database at all.

Qt-free, in keeping with this package: the rule is a plain function precisely
so that it can be pinned without a QApplication.
"""

import pytest

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.ui.widgets._bill_amount_changes_section import parse_amount_change


class TestAnEntryRowThatDescribesAChange:
    def test_a_plain_amount_parses(self) -> None:
        change = parse_amount_change(year=2026, month=9, amount_text="106")
        assert change.effective_year == 2026
        assert change.effective_month == 9
        assert change.new_amount == Amount.from_pounds(106)

    def test_pence_are_kept(self) -> None:
        change = parse_amount_change(year=2026, month=9, amount_text="106.45")
        assert change.new_amount == Amount(pence=10645)

    def test_surrounding_space_is_ignored(self) -> None:
        """The box is read after a strip, so a stray space is not a rejection."""
        change = parse_amount_change(year=2026, month=9, amount_text="  106  ")
        assert change.new_amount == Amount.from_pounds(106)


class TestAnEntryRowThatDoesNot:
    @pytest.mark.parametrize("text", ["abc", "", "1.2.3", "one hundred"])
    def test_unparseable_text_is_refused_rather_than_guessed_at(
        self, text: str
    ) -> None:
        assert parse_amount_change(year=2026, month=9, amount_text=text) is None

    def test_an_impossible_month_is_refused(self) -> None:
        """The value object owns the month rule; this only has to not swallow it."""
        assert parse_amount_change(year=2026, month=13, amount_text="106") is None
