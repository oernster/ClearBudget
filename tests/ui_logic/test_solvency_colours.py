"""Qt-free regression tests for the Solvency month-colour rule.

The colour logic lives in the UI layer but is pure Python, so it is tested
here WITHOUT a QApplication (the widget-level UI tests were removed as fragile).

The rule the title bar must obey:
  * a FUTURE month is coloured by its own within-month health, the same
    _build_month_cashflow_summary engine that colours the Forward Projection
    rows: green if it stays comfortable, amber if it dips low or runs at a loss
    but stays in the black, red only if that month's own balance drops below
    zero. Because it only ever looks at that month, a looming overdraft in a
    LATER month can never turn the title red;
  * the CURRENT month is coloured by its live/actual balance, not a
    re-simulation of the whole month from a stale projected opening.
"""

from types import SimpleNamespace

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.views._solvency_panel_display import SolvencyPanelDisplayMixin
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)

RED = "#f87171"
AMBER = "#fbbf24"
AT_RISK = "#f59e0b"  # the "into the overdraft, but within facility" amber
GREEN = "#34d399"
_BANK = 1


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
    total = sum(i.amount.pence for i in incomes)
    return SimpleNamespace(
        bills=tuple(bills),
        income_sources=tuple(incomes),
        total_income=Amount(pence=total),
    )


# --------------------------------------------------------------------------
# The classifier engine (feeds both the Forward Projection rows and the title).
# --------------------------------------------------------------------------


def test_overdrawn_midmonth_is_red_even_when_closing_positive() -> None:
    """Opens positive, dips overdrawn on day 1, income on day 20 lifts it back
    to a positive close. With no overdraft facility this is RED: the positive
    close must not hide the mid-month overdraft."""
    mix = SolvencyPanelNarrativeMixin()
    summary = _summary([_bank_bill(170000, 1)], [_income(170000, 20)])

    text, color, clarion = mix._build_month_cashflow_summary(
        50000, summary, 170000 - 170000, overdraft_limit_pence=0
    )

    assert color == RED
    assert "OVERDRAWN" in text
    assert clarion is True
    assert "Closes: £500.00" in text


def test_dips_low_but_stays_positive_is_amber() -> None:
    """Never goes negative, but the low point is shallow against the monthly
    drain: a warning, so amber."""
    mix = SolvencyPanelNarrativeMixin()
    summary = _summary([_bank_bill(25000, 1)], [_income(20000, 20)])

    _, color, clarion = mix._build_month_cashflow_summary(
        30000, summary, 25000 - 20000, overdraft_limit_pence=0
    )

    assert color == AMBER
    assert clarion is False


def test_comfortable_month_is_green() -> None:
    """Stays comfortably positive all month -> green."""
    mix = SolvencyPanelNarrativeMixin()
    summary = _summary([_bank_bill(5000, 1)], [_income(5000, 20)])

    _, color, clarion = mix._build_month_cashflow_summary(
        200000, summary, 0, overdraft_limit_pence=0
    )

    assert color == GREEN
    assert clarion is False


def test_overdrawn_within_facility_is_amber() -> None:
    """A mid-month dip that stays inside an agreed overdraft is amber, not red:
    the facility makes it manageable."""
    mix = SolvencyPanelNarrativeMixin()
    summary = _summary([_bank_bill(80000, 1)], [_income(80000, 20)])

    _, color, _ = mix._build_month_cashflow_summary(
        50000, summary, 0, overdraft_limit_pence=50000
    )

    assert color == AMBER


# --------------------------------------------------------------------------
# The title-bar colour dispatcher (current month vs future month).
# --------------------------------------------------------------------------


class _TitleColour(SolvencyPanelNarrativeMixin, SolvencyPanelDisplayMixin):
    """Combines the two UI mixins so _title_health_color can run without Qt."""

    def __init__(self, *, current_summary=None, opening_pence: int = 0) -> None:
        budget_service = SimpleNamespace(
            get_projected_starting_balance_pence=(lambda *, year_month: opening_pence)
        )
        self.view_model = SimpleNamespace(
            current_summary=current_summary, budget_service=budget_service
        )


def _report(balance_pence: int, month: YearMonth) -> SimpleNamespace:
    return SimpleNamespace(balance_pence=balance_pence, year_month=month)


def test_current_month_uses_live_balance_and_is_green_when_safe() -> None:
    """The July bug: the current month is judged on its live balance, so a
    healthy close is green (never a re-simulated red)."""
    harness = _TitleColour()
    report = _report(179385, YearMonth(2026, 7))

    color = harness._title_health_color(
        report, is_current_month=True, overdraft_limit_pence=0
    )

    assert color == GREEN


def test_future_month_that_dips_low_but_stays_positive_is_amber() -> None:
    """The August case: a future month is coloured by its own within-month
    health. It dips low but never below zero, so it is amber, regardless of any
    later month's overdraft (the title only ever sees this month)."""
    summary = _summary([_bank_bill(25000, 1)], [_income(20000, 20)])
    harness = _TitleColour(current_summary=summary, opening_pence=30000)
    report = _report(25000, YearMonth(2026, 8))

    color = harness._title_health_color(
        report, is_current_month=False, overdraft_limit_pence=0
    )

    assert color == AMBER


def test_future_month_that_goes_overdrawn_is_red() -> None:
    """A future month whose own balance actually drops below zero is red."""
    summary = _summary([_bank_bill(170000, 1)], [_income(170000, 20)])
    harness = _TitleColour(current_summary=summary, opening_pence=50000)
    report = _report(50000, YearMonth(2026, 8))

    color = harness._title_health_color(
        report, is_current_month=False, overdraft_limit_pence=0
    )

    assert color == RED


def test_future_month_without_summary_falls_back_to_close_balance() -> None:
    """With no summary to simulate, the close-balance health colour is used."""
    harness = _TitleColour(current_summary=None)
    report = _report(-5000, YearMonth(2026, 8))

    color = harness._title_health_color(
        report, is_current_month=False, overdraft_limit_pence=0
    )

    assert color == RED


# --------------------------------------------------------------------------
# The overdraft floor: red only below the agreed facility, amber within it.
# --------------------------------------------------------------------------


def test_current_month_within_overdraft_facility_is_amber() -> None:
    """A live balance in the red but within an agreed facility is amber, not
    red: the facility makes it manageable."""
    harness = _TitleColour()
    report = _report(-20000, YearMonth(2026, 7))  # -£200, inside a £500 facility

    color = harness._title_health_color(
        report, is_current_month=True, overdraft_limit_pence=50000
    )

    assert color == AT_RISK


def test_current_month_beyond_overdraft_facility_is_red() -> None:
    """A live balance past the agreed facility is red."""
    harness = _TitleColour()
    report = _report(-60000, YearMonth(2026, 7))  # -£600, beyond a £500 facility

    color = harness._title_health_color(
        report, is_current_month=True, overdraft_limit_pence=50000
    )

    assert color == RED


def test_current_month_below_zero_with_no_facility_is_red() -> None:
    """With no facility the floor is zero, so any negative balance is red."""
    harness = _TitleColour()
    report = _report(-100, YearMonth(2026, 7))

    color = harness._title_health_color(
        report, is_current_month=True, overdraft_limit_pence=0
    )

    assert color == RED
