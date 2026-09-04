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

from types import SimpleNamespace

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


def _summary(bills, incomes) -> SimpleNamespace:
    """Minimal stand-in for MonthSummary, as the colours tests use."""
    return SimpleNamespace(
        bills=tuple(bills),
        income_sources=tuple(incomes),
        total_income=Amount(pence=sum(i.amount.pence for i in incomes)),
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
        assert f"Low point: {fmt(20_000)} on day 5" in lines
        assert f"Balance at end of month: {fmt(40_000)}" in lines

    def test_a_month_that_only_rises_is_lowest_at_its_opening(self) -> None:
        lines = _build(
            _OPENING_PENCE,
            [_income(name="Salary", pence=50_000, day=10)],
            [],
        )
        assert f"Low point: {fmt(_OPENING_PENCE)} at the start" in lines

    def test_a_negative_low_is_reported_rather_than_hidden(self) -> None:
        lines = _build(
            _OPENING_PENCE,
            [_income(name="Salary", pence=200_000, day=25)],
            [_bill(name="Rent", pence=150_000, day=3)],
        )
        assert f"Low point: -{fmt(50_000)} on day 3" in lines
        assert f"Balance at end of month: {fmt(150_000)}" in lines

    def test_the_low_is_stated_immediately_before_the_closing_balance(self) -> None:
        lines = _build(
            _OPENING_PENCE,
            [_income(name="Salary", pence=50_000, day=10)],
            [_bill(name="Rent", pence=80_000, day=5)],
        )
        assert lines[-2].startswith("Low point: ")
        assert lines[-1].startswith("Balance at end of month:")


class TestGapClause:
    """The shared clause naming what a month needs or what it spares."""

    def test_a_month_short_of_its_bills_names_the_amount(self) -> None:
        clause = SolvencyPanelNarrativeMixin._gap_clause(66_687)
        assert clause == f"needs {fmt(66_687)} more to hold flat"

    def test_a_month_in_surplus_names_the_headroom(self) -> None:
        clause = SolvencyPanelNarrativeMixin._gap_clause(-50_000)
        assert clause == f"pays for itself, {fmt(50_000)} to spare"

    def test_a_month_that_breaks_even_says_so_without_a_figure(self) -> None:
        assert SolvencyPanelNarrativeMixin._gap_clause(0) == "pays for itself exactly"

    def test_a_healthy_forward_month_still_states_its_margin(self) -> None:
        """The complaint this answers.

        A figure shown only for months in trouble makes the healthy ones look
        as though they have none, which is what made the low point read
        inconsistently before it was given to every month. The clause the
        block closes on has since changed from the hold-flat gap to the money
        that would keep the month afloat; the invariant it was written to
        protect has not, so a healthy month still ends on a figure.
        """
        mix = SolvencyPanelNarrativeMixin()
        summary = _summary([_bill(name="Rent", pence=50_000, day=5)], [])
        text, _, _ = mix._build_month_cashflow_summary(
            _OPENING_PENCE, summary, -50_000, overdraft_limit_pence=0
        )
        assert f"Stays afloat, {fmt(50_000)} clear at its lowest" in text

    def test_the_forward_block_no_longer_reports_the_hold_flat_gap(self) -> None:
        """A month running at a loss that never goes near the red.

        The gap is a true statement about the month's shape and a useless one
        as a rescue figure, so it left the forward blocks. It is still the
        clause the displayed month's own gap label is built from, which is why
        _gap_clause is asserted here rather than deleted with the line.
        """
        mix = SolvencyPanelNarrativeMixin()
        summary = _summary(
            [_bill(name="Rent", pence=50_000, day=5)],
            [_income(name="Salary", pence=33_313, day=20)],
        )
        text, _, _ = mix._build_month_cashflow_summary(
            _OPENING_PENCE, summary, 16_687, overdraft_limit_pence=0
        )
        assert "hold flat" not in text
        assert f"Stays afloat, {fmt(50_000)} clear at its lowest" in text
        assert "Closes:" in text
        assert SolvencyPanelNarrativeMixin._gap_clause(16_687) == (
            f"needs {fmt(16_687)} more to hold flat"
        )
