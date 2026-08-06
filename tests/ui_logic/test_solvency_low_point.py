"""The displayed month's balance breakdown reports its lowest point.

The Forward Projection lines have always carried a low for the two months
ahead, because the engine behind them tracks a running minimum. The breakdown
for the month you are actually looking at did not: it walked the same day
ordered events but only ever emitted a line per income event plus a closing
figure, so the month in front of you was the one month whose worst point was
never stated. On the current month that is the figure that matters most.

Qt-free: the builder is a static method over plain data, so these run without
a QApplication (see this package's docstring).
"""

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils.format_helpers import fmt
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)

_BANK = 1
_OPENING_PENCE = 100_000


def _bill(*, name: str, pence: int, day: int) -> Bill:
    return Bill(
        id=1,
        name=name,
        amount=Amount(pence=pence),
        payment_method_id=_BANK,
        category="housing",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
    )


def _income(*, name: str, pence: int, day: int) -> IncomeSource:
    return IncomeSource(
        id=1,
        name=name,
        amount=Amount(pence=pence),
        is_reliable=True,
        day_of_month=day,
    )


def _build(opening_pence, income_sources, bills) -> list[str]:
    return SolvencyPanelNarrativeMixin._build_income_timeline(
        opening_pence, income_sources, bills
    )


class TestLowestPointIsReported:
    def test_the_low_falls_on_a_bill_day_that_has_no_line_of_its_own(self) -> None:
        """The regression this exists for.

        Only income events get their own line, so a month bottoming out on a
        bill day had a worst point that appeared nowhere on screen.
        """
        lines = _build(
            _OPENING_PENCE,
            [_income(name="Salary", pence=50_000, day=10)],
            [
                _bill(name="Rent", pence=80_000, day=5),
                _bill(name="Council tax", pence=30_000, day=20),
            ],
        )
        # Day 5 leaves 20,000; day 10 lifts it to 70,000; day 20 closes at 40,000.
        assert f"Lowest point (day 5): {fmt(20_000)}" in lines
        assert f"Balance at end of month: {fmt(40_000)}" in lines

    def test_a_month_that_only_rises_is_lowest_at_its_opening(self) -> None:
        lines = _build(
            _OPENING_PENCE,
            [_income(name="Salary", pence=50_000, day=10)],
            [],
        )
        assert f"Lowest point (at the start): {fmt(_OPENING_PENCE)}" in lines

    def test_a_negative_low_is_reported_rather_than_hidden(self) -> None:
        lines = _build(
            _OPENING_PENCE,
            [_income(name="Salary", pence=200_000, day=25)],
            [_bill(name="Rent", pence=150_000, day=3)],
        )
        assert f"Lowest point (day 3): {fmt(-50_000)}" in lines
        assert f"Balance at end of month: {fmt(150_000)}" in lines

    def test_the_low_is_stated_immediately_before_the_closing_balance(self) -> None:
        lines = _build(
            _OPENING_PENCE,
            [_income(name="Salary", pence=50_000, day=10)],
            [_bill(name="Rent", pence=80_000, day=5)],
        )
        assert lines[-2].startswith("Lowest point (")
        assert lines[-1].startswith("Balance at end of month:")
