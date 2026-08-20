"""The gap specification: what has to arrive for the projection page to hold.

A second projection without that list would be a wish rather than a plan, so
these pin what it names and how it names an expectation with no day on it.

Qt-free: the builder is a plain function over plain data, so these run without
a QApplication (see this package's docstring).
"""

from types import SimpleNamespace

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.views._solvency_panel_assumed import SolvencyPanelAssumedMixin


class _Block(SolvencyPanelAssumedMixin):
    """The mixin that renders the assumed block."""


def _expected(name: str, pence: int, day):
    return (
        YearMonth(2026, 10),
        SimpleNamespace(name=name, amount=Amount(pence=pence), day_of_month=day),
    )


class TestGapSpecification:
    def test_it_names_the_amount_and_the_day_it_must_arrive_by(self):
        text = _Block._gap_specification([_expected("Family top-up", 60000, 10)])
        assert "Depends on money not yet received:" in text
        assert "October 2026: Family top-up" in text
        assert "by day 10" in text

    def test_an_undated_expectation_says_so_rather_than_inventing_a_day(self):
        text = _Block._gap_specification([_expected("Family top-up", 60000, None)])
        assert "at any point" in text
        assert "day None" not in text

    def test_every_expected_item_is_listed(self):
        text = _Block._gap_specification(
            [_expected("Top-up", 60000, 10), _expected("Refund", 2500, 3)]
        )
        assert "Top-up" in text
        assert "Refund" in text
