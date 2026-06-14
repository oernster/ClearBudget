"""Headless smoke tests for the credit card view and dialog.

The UI layer is coverage-exempt; these guard the scheduled-limit-change UI
against runtime errors (the card-row pill, the projection strip's per-month
limit, and the dialog's change list).
"""

from PySide6.QtCore import QDate

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.credit_limit_change import CreditLimitChange
from clear_budget.ui.views.credit_card_view import CreditCardView
from clear_budget.ui.widgets.credit_card_dialog import CreditCardDialog
from tests.application.fakes import (
    FakeBillRepository,
    FakeIncomeSourceRepository,
    FakePaymentMethodRepository,
)


def _service(cards):
    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    pm_repo = FakePaymentMethodRepository(_cards=list(cards))
    return BudgetService(
        bill_repo, income_repo, pm_repo, MonthGenerator(bill_repo, income_repo)
    )


def _card(changes=()):
    return CreditCard(
        id=2,
        name="CapitalOne",
        credit_limit=Amount(pence=175000),
        current_balance_used=Amount(pence=152398),
        interest_rate_apr=25.69,
        payment_due_day=1,
        scheduled_limit_changes=tuple(changes),
    )


def _change(year=2026, month=8, day=1, pence=250000):
    return CreditLimitChange(
        effective_year=year,
        effective_month=month,
        effective_day=day,
        new_limit=Amount(pence=pence),
    )


def test_view_builds_with_scheduled_change(qapplication) -> None:
    view = CreditCardView(_service([_card([_change()])]))
    assert view.projection_table.columnCount() == 1


def test_view_builds_without_changes(qapplication) -> None:
    view = CreditCardView(_service([_card()]))
    assert view.projection_table.columnCount() == 1


def test_view_builds_with_multiple_scheduled_changes(qapplication) -> None:
    card = _card([_change(2026, 8, 1, 250000), _change(2026, 10, 1, 300000)])
    view = CreditCardView(_service([card]))
    assert view.projection_table.columnCount() == 1


def test_view_future_month_with_midmonth_change_builds(qapplication) -> None:
    from clear_budget.domain.value_objects.year_month import YearMonth

    view = CreditCardView(_service([_card([_change(2026, 8, 15, 250000)])]))
    view.set_month(YearMonth(2026, 8))
    assert view.projection_table.columnCount() == 1


def test_solvency_panel_bar_uses_displayed_month_end_limit(qapplication) -> None:
    from PySide6.QtWidgets import QProgressBar
    from clear_budget.application.dto.solvency_report import SolvencyReport
    from clear_budget.domain.value_objects.year_month import YearMonth
    from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
    from clear_budget.ui.views.solvency_panel import SolvencyPanel

    # A 15 Jul increase is NOT reflected in June's bar: June's own month-end limit
    # is still the £1,750 base (the pills carry the heads-up instead).
    svc = _service([_card([_change(2026, 7, 15, 500000)])])
    panel = SolvencyPanel(SolvencyViewModel(budget_service=svc))
    report = SolvencyReport(
        year_month=YearMonth(2026, 6),
        balance_pence=0,
        deficit=Amount.zero(),
        buffer=Amount.zero(),
        forward_shortfall=Amount.zero(),
        desired_acquire=Amount.zero(),
        is_solvent=True,
        first_negative_day=None,
    )
    panel._rebuild_card_bars(report)
    bars = [
        panel.card_bars_layout.itemAt(i).widget()
        for i in range(panel.card_bars_layout.count())
    ]
    progress = [b for b in bars if isinstance(b, QProgressBar)]
    assert progress and progress[0].maximum() == 175000


def test_solvency_future_deficit_alert_states_runway(qapplication) -> None:
    """A future deficit month surfaces the monthly drain and the overdraft month."""
    from clear_budget.application.dto.solvency_report import SolvencyReport
    from clear_budget.domain.entities.bill import Bill
    from clear_budget.domain.entities.income_source import IncomeSource
    from clear_budget.domain.value_objects.year_month import YearMonth
    from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
    from clear_budget.ui.views.solvency_panel import SolvencyPanel

    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    bill_repo.add(
        bill=Bill(
            id=1,
            name="Rent",
            amount=Amount(pence=150000),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=None,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
    )
    income_repo.add(
        income=IncomeSource(
            id=1,
            name="UC",
            amount=Amount(pence=100000),
            is_reliable=True,
            day_of_month=None,
        )
    )
    svc = BudgetService(
        bill_repo,
        income_repo,
        FakePaymentMethodRepository(),
        MonthGenerator(bill_repo, income_repo),
    )
    future = YearMonth(2026, 9)
    panel = SolvencyPanel(SolvencyViewModel(budget_service=svc))
    panel.view_model.current_summary = svc.get_month_summary(year_month=future)
    report = SolvencyReport(
        year_month=future,
        balance_pence=90000,
        deficit=Amount.zero(),
        buffer=Amount.zero(),
        forward_shortfall=Amount.zero(),
        desired_acquire=Amount.zero(),
        is_solvent=True,
        first_negative_day=None,
    )
    panel.update_display(report)
    text = panel.overdraft_alert.text()
    # Net -500/month from 900: Oct 400, Nov -100 -> overdrawn by November.
    assert "savings falling" in text
    assert "overdrawn by November 2026" in text


def test_solvency_banner_clarions_unfunded_next_month_overdraft(qapplication) -> None:
    """With no facility, a next-month overdraft escalates the banner to a red
    clarion naming the month and the missing facility, on the banner and the
    mid-month alert alike."""
    from clear_budget.application.dto.solvency_report import SolvencyReport
    from clear_budget.domain.entities.bill import Bill
    from clear_budget.domain.entities.income_source import IncomeSource
    from clear_budget.domain.value_objects.year_month import YearMonth
    from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
    from clear_budget.ui.views.solvency_panel import SolvencyPanel

    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    bill_repo.add(
        bill=Bill(
            id=1,
            name="Rent",
            amount=Amount(pence=120000),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
    )
    income_repo.add(
        income=IncomeSource(
            id=1,
            name="UC",
            amount=Amount(pence=100000),
            is_reliable=True,
            day_of_month=20,
        )
    )
    svc = BudgetService(
        bill_repo,
        income_repo,
        FakePaymentMethodRepository(),
        MonthGenerator(bill_repo, income_repo),
    )
    panel = SolvencyPanel(SolvencyViewModel(budget_service=svc))
    panel.view_model.current_summary = svc.get_month_summary(
        year_month=YearMonth(2026, 7)
    )
    report = SolvencyReport(
        year_month=YearMonth(2026, 7),
        balance_pence=50000,
        deficit=Amount.zero(),
        buffer=Amount.zero(),
        forward_shortfall=Amount.zero(),
        desired_acquire=Amount.zero(),
        is_solvent=True,
        first_negative_day=None,
    )
    panel.update_display(report)

    text = panel.overdraft_alert.text()
    assert "overdrawn in August" in text
    assert "NO OVERDRAFT FACILITY" in text
    assert "#f87171" in panel.overdraft_alert.styleSheet()
    assert "NO OVERDRAFT FACILITY" in panel.midmonth_alert.text()


def test_cashflow_summary_overdraft_facility_severity(qapplication) -> None:
    """No facility (or exceeded) is a red clarion; within a facility is amber."""
    from clear_budget.domain.entities.bill import Bill
    from clear_budget.domain.entities.income_source import IncomeSource
    from clear_budget.domain.value_objects.year_month import YearMonth
    from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
    from clear_budget.ui.views.solvency_panel import SolvencyPanel

    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    bill_repo.add(
        bill=Bill(
            id=1,
            name="Rent",
            amount=Amount(pence=120000),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
    )
    income_repo.add(
        income=IncomeSource(
            id=1,
            name="UC",
            amount=Amount(pence=150000),
            is_reliable=True,
            day_of_month=20,
        )
    )
    svc = BudgetService(
        bill_repo,
        income_repo,
        FakePaymentMethodRepository(),
        MonthGenerator(bill_repo, income_repo),
    )
    panel = SolvencyPanel(SolvencyViewModel(budget_service=svc))
    summary = svc.get_month_summary(year_month=YearMonth(2026, 8))
    # Opens 500: day 1 -1200 -> -700 dip, day 20 +1500 -> +800 close.

    text, color, clarion = panel._build_month_cashflow_summary(50000, summary, 70000, 0)
    assert clarion is True
    assert color == "#f87171"
    assert "NO OVERDRAFT FACILITY" in text

    text_f, color_f, clarion_f = panel._build_month_cashflow_summary(
        50000, summary, 70000, 80000
    )
    assert clarion_f is False
    assert color_f == "#fbbf24"
    assert "Within your" in text_f

    text_x, color_x, clarion_x = panel._build_month_cashflow_summary(
        50000, summary, 70000, 50000
    )
    assert clarion_x is True
    assert "EXCEEDS" in text_x


def test_dialog_loads_existing_changes(qapplication) -> None:
    dialog = CreditCardDialog(None, _card([_change()]))
    changes = dialog.get_limit_changes()
    assert len(changes) == 1
    assert changes[0].new_limit.pence == 250000


def test_dialog_add_and_remove_change(qapplication) -> None:
    dialog = CreditCardDialog(None, _card())
    dialog.change_date_edit.setDate(QDate(2030, 9, 15))
    dialog.change_limit_edit.setText("3000.00")
    dialog._on_add_change()
    assert len(dialog.get_limit_changes()) == 1
    dialog._on_remove_change(0)
    assert len(dialog.get_limit_changes()) == 0


def test_dialog_flags_downward_change_below_balance(qapplication) -> None:
    dialog = CreditCardDialog(None, _card())
    dialog.change_date_edit.setDate(QDate(2030, 9, 1))
    dialog.change_limit_edit.setText("500.00")
    dialog._on_add_change()
    assert not dialog.change_warning_label.isHidden()
    assert "over its limit" in dialog.change_warning_label.text()
