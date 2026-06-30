"""Regression tests pinning the Solvency title-bar colour to the month's own
within-month cashflow health.

The bug these guard against: a month that dips OVERDRAWN partway through the
month but happens to CLOSE positive (e.g. a big bill on day 1, income on day
20) was coloured amber in the title bar, because the title was keyed off the
closing balance. Solvency's own Forward Projection correctly shows such a month
red. The title bar MUST render the same colour Solvency shows for that month.

Two layers:
  * engine tests drive SolvencyPanelNarrativeMixin._build_month_cashflow_summary
    directly with an explicit opening balance, so the red/amber/green rule is
    locked deterministically and free of any calendar coupling;
  * panel tests drive the real SolvencyPanel on a real SQLite database and
    assert the month/year title label renders that same colour, and that it
    equals the colour the Forward Projection gives the very same month.
"""

import re
from types import SimpleNamespace

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.application.services._settings_operations import (
    set_bank_balance_pence,
)
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)
from clear_budget.ui.views.solvency_panel import SolvencyPanel

RED = "#f87171"
AMBER = "#fbbf24"
GREEN = "#34d399"
_BANK = 1


def _color_of(stylesheet: str) -> str:
    """Pull the text-colour hex out of a label stylesheet (not background)."""
    match = re.search(r"(?<!-)color:\s*(#[0-9a-fA-F]{6})", stylesheet)
    return match.group(1).lower() if match else ""


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
# Engine-level rule (deterministic, no calendar, no Qt).
# --------------------------------------------------------------------------


def test_overdrawn_midmonth_is_red_even_when_closing_positive() -> None:
    """The core bug: opens positive, dips overdrawn on day 1, income on day 20
    lifts it back to a positive close. With no overdraft facility this is RED,
    NOT amber - the close being positive must not hide the mid-month overdraft.
    """
    mix = SolvencyPanelNarrativeMixin()
    opening = 50000  # £500
    summary = _summary([_bank_bill(170000, 1)], [_income(170000, 20)])
    drain = 170000 - 170000  # net zero across the month

    text, color, clarion = mix._build_month_cashflow_summary(
        opening, summary, drain, overdraft_limit_pence=0
    )

    assert color == RED, f"overdrawn-midmonth must be red, got {color}"
    assert "OVERDRAWN" in text
    assert clarion is True
    # Proves the close really is positive, so red is driven by the dip alone.
    assert "Closes: £500.00" in text


def test_dips_low_but_stays_positive_is_amber() -> None:
    """Never goes negative, but the low point is shallow against the monthly
    drain - a warning, so amber (this is the July case)."""
    mix = SolvencyPanelNarrativeMixin()
    opening = 30000  # £300
    summary = _summary([_bank_bill(25000, 1)], [_income(20000, 20)])
    drain = 25000 - 20000  # £50 deficit

    _, color, clarion = mix._build_month_cashflow_summary(
        opening, summary, drain, overdraft_limit_pence=0
    )

    assert color == AMBER, f"low-but-positive must be amber, got {color}"
    assert clarion is False


def test_comfortable_month_is_green() -> None:
    """Stays comfortably positive all month -> green."""
    mix = SolvencyPanelNarrativeMixin()
    opening = 200000  # £2000
    summary = _summary([_bank_bill(5000, 1)], [_income(5000, 20)])

    _, color, clarion = mix._build_month_cashflow_summary(
        opening, summary, 0, overdraft_limit_pence=0
    )

    assert color == GREEN
    assert clarion is False


def test_overdrawn_within_facility_is_amber() -> None:
    """A mid-month dip that stays inside an agreed overdraft is amber, not
    red: the facility makes it manageable."""
    mix = SolvencyPanelNarrativeMixin()
    opening = 50000
    summary = _summary([_bank_bill(80000, 1)], [_income(80000, 20)])

    _, color, _ = mix._build_month_cashflow_summary(
        opening, summary, 0, overdraft_limit_pence=50000
    )

    assert color == AMBER


# --------------------------------------------------------------------------
# Panel-level: the real title bar, on a real database.
# --------------------------------------------------------------------------


def _build_service(tmp_path, *, bank_pence, bills, incomes) -> BudgetService:
    db = Database(tmp_path / "title.db")
    db.connect()
    db.create_schema()
    bill_repo = SQLiteBillRepository(db.conn)
    income_repo = SQLiteIncomeSourceRepository(db.conn)
    pm_repo = SQLitePaymentMethodRepository(db.conn)
    for bill in bills:
        bill_repo.add(bill=bill)
    for inc in incomes:
        income_repo.add(income=inc)
    set_bank_balance_pence(db.conn, bank_pence)
    return BudgetService(
        bill_repo=bill_repo,
        income_repo=income_repo,
        payment_method_repo=pm_repo,
        month_generator=MonthGenerator(bill_repo, income_repo),
    )


def _future_month() -> YearMonth:
    """A month well clear of the current one, so the title reflects a pure
    forward projection regardless of when the test runs."""
    ym = YearMonth.today()
    for _ in range(4):
        ym = ym.next_month()
    return ym


def test_title_bar_is_red_for_overdrawn_midmonth_closing_positive(
    qapplication, tmp_path
) -> None:
    """End to end: a month that overdraws mid-month but closes positive paints
    the title-bar month label RED. This is the exact scenario that was wrongly
    amber."""
    # £1700 bill on day 1, £1700 income on day 20: net zero, so every future
    # month opens at the £500 bank balance, dips to -£1200 on day 1, recovers
    # to a +£500 close. No overdraft facility -> red.
    svc = _build_service(
        tmp_path,
        bank_pence=50000,
        bills=[_bank_bill(170000, 1)],
        incomes=[_income(170000, 20)],
    )
    month = _future_month()
    vm = SolvencyViewModel(budget_service=svc, current_month=month)
    panel = SolvencyPanel(vm)
    vm.set_month(month)

    assert _color_of(panel.month_label.styleSheet()) == RED


def test_title_bar_color_equals_forward_projection_color(
    qapplication, tmp_path
) -> None:
    """The invariant: the title bar for a month renders the SAME colour the
    Forward Projection gives that very month (viewed from the month before).
    Locks 'the title matches what Solvency says for that month'."""
    svc = _build_service(
        tmp_path,
        bank_pence=50000,
        bills=[_bank_bill(170000, 1)],
        incomes=[_income(170000, 20)],
    )
    month = _future_month()
    prior = month.previous_month()
    vm = SolvencyViewModel(budget_service=svc, current_month=prior)
    panel = SolvencyPanel(vm)

    # View the prior month: `month` is then the M1 forward-projection row.
    vm.set_month(prior)
    forward_color = _color_of(panel.m1_projection_label.styleSheet())

    # Now view `month` itself: its title bar must render that same colour.
    vm.set_month(month)
    title_color = _color_of(panel.month_label.styleSheet())

    assert title_color == forward_color
    assert title_color == RED
