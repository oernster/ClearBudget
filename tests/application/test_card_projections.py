"""Tests for BudgetService.get_card_monthly_states / get_card_projection_months."""

from datetime import date

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from tests.application.fakes import (
    FakeBillRepository,
    FakeIncomeSourceRepository,
    FakePaymentMethodRepository,
)


def _make_service():
    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    pm_repo = FakePaymentMethodRepository()
    gen = MonthGenerator(bill_repo, income_repo)
    svc = BudgetService(bill_repo, income_repo, pm_repo, gen)
    return svc


class TestCardProjections:
    """Tests for get_card_monthly_states / get_card_projection_months."""

    def test_get_card_monthly_states_for_current_month(self) -> None:
        svc = _make_service()
        today_ym = YearMonth(date.today().year, date.today().month)
        svc.payment_method_repo.add_credit_card(
            card=CreditCard(
                id=1,
                name="Visa",
                credit_limit=Amount(pence=500000),
                current_balance_used=Amount(pence=100000),
                payment_due_day=1,
                active=1,
            )
        )

        states = svc.get_card_monthly_states(year_month=today_ym)

        assert len(states) == 1
        assert states[0].card.name == "Visa"

    def test_get_card_projection_months_returns_n_months(self) -> None:
        svc = _make_service()
        today_ym = YearMonth(date.today().year, date.today().month)
        svc.payment_method_repo.add_credit_card(
            card=CreditCard(
                id=1,
                name="Visa",
                credit_limit=Amount(pence=500000),
                current_balance_used=Amount(pence=100000),
                payment_due_day=1,
                active=1,
            )
        )

        months = svc.get_card_projection_months(start_month=today_ym, n_months=3)

        assert len(months) == 3
        assert all(len(month_states) == 1 for month_states in months)
