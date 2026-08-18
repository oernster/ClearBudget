"""The assumed-income second reading, as text.

Qt-free: both builders are plain functions over plain data, so these run
without a QApplication (see this package's docstring).
"""

from datetime import date
from types import SimpleNamespace

from clear_budget.domain.services.safe_to_spend import CapacityStep
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.views._solvency_panel_assumed import SolvencyPanelAssumedMixin
from clear_budget.ui.views._solvency_panel_safe_to_spend import (
    SolvencyPanelSafeToSpendMixin,
)


class _Block(SolvencyPanelAssumedMixin, SolvencyPanelSafeToSpendMixin):
    """The two mixins that between them render the assumed block."""


def _step(day: int, pence: int, binding: int) -> CapacityStep:
    return CapacityStep(
        from_day=date(2026, 8, day),
        amount_pence=pence,
        binding_day=date(2026, 10, binding),
    )


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


class TestAssumedCapacityText:
    def test_an_expectation_that_changes_nothing_says_so_once(self):
        # Restating an identical schedule would be noise dressed as insight.
        steps = [_step(19, 10189, 14)]
        text = _Block()._assumed_capacity_text(steps, list(steps))
        assert text == (
            "No change: the expected income falls outside what limits you now"
        )

    def test_a_lower_assumed_figure_explains_why_it_is_lower(self):
        # The counterintuitive case: surviving longer means the later months
        # start counting, so expecting MORE money lowers what today allows.
        known = [_step(20, 44561, 14)]
        probable = [_step(20, 37874, 14)]
        text = _Block()._assumed_capacity_text(known, probable)
        assert "£378.74" in text
        assert "Lower than the known figure" in text
        assert "later months now count against today" in text

    def test_a_higher_assumed_figure_is_not_explained_away(self):
        known = [_step(20, 10000, 14)]
        probable = [_step(20, 50000, 14)]
        text = _Block()._assumed_capacity_text(known, probable)
        assert "£500.00" in text
        assert "Lower than the known figure" not in text
