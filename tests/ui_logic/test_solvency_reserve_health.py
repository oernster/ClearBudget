"""Qt-free tests: the reserve reaches the month's sentence AND its colour.

The Forward Projection once said a month paid for itself while the Overall
Health line above it said the same month was short, because each derived what
the month needed from its own sum. Both now read `_month_shortfall_pence`, so
the sentence and the traffic light can no longer disagree.

The guard that matters most here is the last one: a reserve must never move
the BALANCE. Money set aside stays in the account until the commitment is
paid, so a projection that subtracted it would report an overdraft that
cannot happen.
"""

from types import SimpleNamespace

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.theme_tokens import STATE_CAUTION, STATE_SAFE
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)

_BANK = 1
_MONTH = YearMonth(year=2026, month=9)


def _bank_bill(pence: int, day: int) -> Bill:
    return Bill(
        id=day,
        name=f"bill-{day}",
        amount=Amount(pence=pence),
        payment_method_id=_BANK,
        category="x",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
    )


def _income(pence: int, day: int) -> IncomeSource:
    return IncomeSource(
        id=day,
        name=f"income-{day}",
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


def _mix(reserve_pence: int) -> SolvencyPanelNarrativeMixin:
    mix = SolvencyPanelNarrativeMixin()
    mix.view_model = SimpleNamespace(
        budget_service=SimpleNamespace(
            get_month_reserve_cost_pence=(lambda *, year_month: reserve_pence)
        )
    )
    return mix


# A month whose income covers its bills with 100.00 to spare, which is less
# than the 300.00 it has to set aside.
_BILLS = [_bank_bill(150000, 1)]
_INCOMES = [_income(160000, 20)]
_SPARE_PENCE = 10000
_RESERVE_PENCE = 30000
# Clears the day-1 bill with 100.00 standing, so the month never goes
# overdrawn: the overdraft path would decide the state before the health
# rule ever ran; it is the health rule these tests are about.
_OPENING_PENCE = 160000


class TestWhatTheMonthMustFind:
    def test_the_bills_and_the_reserve_are_added_against_the_income(self):
        mix = _mix(_RESERVE_PENCE)
        summary = _summary(_BILLS, _INCOMES)
        assert mix._month_shortfall_pence(_MONTH, summary) == (
            150000 + _RESERVE_PENCE - 160000
        )

    def test_setting_nothing_aside_leaves_the_old_figure(self):
        summary = _summary(_BILLS, _INCOMES)
        assert _mix(0)._month_shortfall_pence(_MONTH, summary) == -_SPARE_PENCE


class TestTheSentence:
    def test_a_month_that_cannot_fund_its_reserve_says_so(self):
        mix = _mix(_RESERVE_PENCE)
        summary = _summary(_BILLS, _INCOMES)
        text, _colour, _clarion = mix._build_month_cashflow_summary(
            _OPENING_PENCE, summary, mix._month_shortfall_pence(_MONTH, summary)
        )
        assert "Needs £200.00 more to hold flat" in text

    def test_the_same_month_without_a_reserve_pays_for_itself(self):
        """The reading before this existed, kept as the contrast."""
        mix = _mix(0)
        summary = _summary(_BILLS, _INCOMES)
        text, _colour, _clarion = mix._build_month_cashflow_summary(
            _OPENING_PENCE, summary, mix._month_shortfall_pence(_MONTH, summary)
        )
        assert "Pays for itself" in text


class TestTheColour:
    """The reserve reaches the traffic light, not only the words beside it."""

    def test_a_reserve_it_cannot_fund_turns_a_safe_month_amber(self):
        summary = _summary(_BILLS, _INCOMES)
        balance = _OPENING_PENCE
        without = _mix(0)
        with_reserve = _mix(_RESERVE_PENCE)
        assert (
            without._month_cashflow_state(
                balance, summary, without._month_shortfall_pence(_MONTH, summary)
            )
            == STATE_SAFE
        )
        assert (
            with_reserve._month_cashflow_state(
                balance, summary, with_reserve._month_shortfall_pence(_MONTH, summary)
            )
            == STATE_CAUTION
        )

    def test_a_balance_that_covers_the_reserve_too_stays_safe(self):
        """Being short is not the trigger; failing to cover it is."""
        mix = _mix(_RESERVE_PENCE)
        summary = _summary(_BILLS, _INCOMES)
        ample = _OPENING_PENCE + 100 * _RESERVE_PENCE
        assert (
            mix._month_cashflow_state(
                ample, summary, mix._month_shortfall_pence(_MONTH, summary)
            )
            == STATE_SAFE
        )


class TestTheBalanceIsUntouched:
    """A reserve is held IN the account; it must never move the projection."""

    def test_the_walk_closes_on_the_same_figure_either_way(self):
        summary = _summary(_BILLS, _INCOMES)
        without = _mix(0)._walk_month(_OPENING_PENCE, summary)
        with_reserve = _mix(_RESERVE_PENCE)._walk_month(_OPENING_PENCE, summary)
        assert without["closing"] == with_reserve["closing"]
        assert without["min_balance"] == with_reserve["min_balance"]

    def test_the_month_still_closes_where_the_bills_alone_leave_it(self):
        summary = _summary(_BILLS, _INCOMES)
        walk = _mix(_RESERVE_PENCE)._walk_month(_OPENING_PENCE, summary)
        assert walk["closing"] == _OPENING_PENCE + 160000 - 150000
