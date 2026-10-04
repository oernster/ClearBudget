"""Every Solvency month says when it goes overdrawn and how far.

The day the account first goes below zero and the deepest it gets were only
readable off the graph. Each month's block now states both on one line; a
month that never goes under says that too.

Qt-free: the helpers are static methods over plain data, so these run without
a QApplication (see this package's docstring).
"""

from types import SimpleNamespace

from clear_budget.application.services._month_walk import walk_month
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


def _bill(*, pence: int, day: int) -> Bill:
    return Bill(
        id=1,
        name="Rent",
        amount=Amount(pence=pence),
        payment_method_id=_BANK,
        category="housing",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
    )


def _income(*, pence: int, day: int) -> IncomeSource:
    return IncomeSource(
        id=1,
        name="Salary",
        amount=Amount(pence=pence),
        is_reliable=True,
        day_of_month=day,
    )


def _summary(bills, incomes) -> SimpleNamespace:
    return SimpleNamespace(
        bills=tuple(bills),
        income_sources=tuple(incomes),
        total_income=Amount(pence=sum(i.amount.pence for i in incomes)),
    )


def _line(opening_pence: int, summary) -> str:
    walk = walk_month(opening_pence, summary)
    return SolvencyPanelNarrativeMixin._overdrawn_line(opening_pence, walk)


class TestOverdrawnLine:
    def test_names_the_first_day_under_and_the_deepest_point(self) -> None:
        summary = _summary(
            [_bill(pence=120_000, day=9), _bill(pence=30_000, day=22)],
            [_income(pence=200_000, day=25)],
        )
        # Day 9 leaves -20,000; day 22 sinks to -50,000; day 25 recovers.
        assert _line(_OPENING_PENCE, summary) == (
            f"Overdrawn from day 9; at worst {fmt(50_000)} overdrawn on day 22"
        )

    def test_a_month_that_stays_in_credit_says_so(self) -> None:
        summary = _summary([_bill(pence=50_000, day=5)], [])
        assert _line(_OPENING_PENCE, summary) == "Never overdrawn"

    def test_a_month_opening_overdrawn_is_overdrawn_from_the_start(self) -> None:
        summary = _summary([_bill(pence=10_000, day=12)], [])
        assert _line(-30_000, summary) == (
            f"Overdrawn from the start; at worst {fmt(40_000)} overdrawn on day 12"
        )

    def test_the_worst_can_be_the_opening_itself(self) -> None:
        summary = _summary([], [_income(pence=50_000, day=3)])
        assert _line(-30_000, summary) == (
            f"Overdrawn from the start; at worst {fmt(30_000)} overdrawn at the start"
        )

    def test_the_line_leads_every_forward_month_block(self) -> None:
        mix = SolvencyPanelNarrativeMixin()
        summary = _summary([_bill(pence=150_000, day=4)], [])
        text, _, _ = mix._build_month_cashflow_summary(
            _OPENING_PENCE, summary, 150_000, overdraft_limit_pence=0
        )
        assert text.split("\n")[0] == (
            f"Overdrawn from day 4; at worst {fmt(50_000)} overdrawn on day 4"
        )
