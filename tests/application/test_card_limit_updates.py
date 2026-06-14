"""Tests for elapsed credit limit change auto-apply and the service wrappers."""

from datetime import date

from clear_budget.application.services._card_limit_updates import (
    apply_elapsed_limit_changes,
)
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.credit_limit_change import CreditLimitChange
from tests.application.fakes import (
    FakeBillRepository,
    FakeIncomeSourceRepository,
    FakePaymentMethodRepository,
)


def _change(year: int, month: int, day: int, pence: int) -> CreditLimitChange:
    return CreditLimitChange(
        effective_year=year,
        effective_month=month,
        effective_day=day,
        new_limit=Amount(pence=pence),
    )


def _card(changes=(), limit_pence: int = 50000) -> CreditCard:
    return CreditCard(
        id=2,
        name="Card",
        credit_limit=Amount(pence=limit_pence),
        current_balance_used=Amount(pence=0),
        scheduled_limit_changes=tuple(changes),
    )


def _make_service(cards):
    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    pm_repo = FakePaymentMethodRepository(_cards=list(cards))
    gen = MonthGenerator(bill_repo, income_repo)
    return BudgetService(bill_repo, income_repo, pm_repo, gen), pm_repo


class TestApplyElapsedLimitChanges:
    def test_no_changes_is_noop(self) -> None:
        _svc, pm_repo = _make_service([_card()])
        apply_elapsed_limit_changes(pm_repo, today=date(2026, 6, 20))
        updated = pm_repo.get_credit_card_by_id(card_id=2)
        assert updated.credit_limit.pence == 50000
        assert updated.scheduled_limit_changes == ()

    def test_future_change_not_applied(self) -> None:
        _svc, pm_repo = _make_service([_card([_change(2026, 6, 15, 100000)])])
        apply_elapsed_limit_changes(pm_repo, today=date(2026, 6, 10))
        updated = pm_repo.get_credit_card_by_id(card_id=2)
        assert updated.credit_limit.pence == 50000
        assert len(updated.scheduled_limit_changes) == 1

    def test_elapsed_change_folds_into_limit(self) -> None:
        _svc, pm_repo = _make_service([_card([_change(2026, 6, 15, 100000)])])
        apply_elapsed_limit_changes(pm_repo, today=date(2026, 6, 20))
        updated = pm_repo.get_credit_card_by_id(card_id=2)
        assert updated.credit_limit.pence == 100000
        assert updated.scheduled_limit_changes == ()

    def test_multiple_elapsed_takes_latest_and_keeps_future(self) -> None:
        card = _card(
            [
                _change(2026, 6, 15, 100000),
                _change(2026, 7, 4, 120000),
                _change(2026, 9, 1, 150000),
            ]
        )
        _svc, pm_repo = _make_service([card])
        apply_elapsed_limit_changes(pm_repo, today=date(2026, 7, 10))
        updated = pm_repo.get_credit_card_by_id(card_id=2)
        assert updated.credit_limit.pence == 120000
        assert len(updated.scheduled_limit_changes) == 1
        assert updated.scheduled_limit_changes[0].new_limit.pence == 150000


class TestBudgetServiceLimitWrappers:
    def test_apply_wrapper_folds(self) -> None:
        svc, pm_repo = _make_service([_card([_change(2026, 6, 15, 100000)])])
        svc.apply_elapsed_limit_changes(today=date(2026, 6, 20))
        assert pm_repo.get_credit_card_by_id(card_id=2).credit_limit.pence == 100000

    def test_set_credit_limit_changes_replaces(self) -> None:
        svc, pm_repo = _make_service([_card()])
        svc.set_credit_limit_changes(card_id=2, changes=[_change(2026, 8, 1, 200000)])
        updated = pm_repo.get_credit_card_by_id(card_id=2)
        assert len(updated.scheduled_limit_changes) == 1
        assert updated.scheduled_limit_changes[0].new_limit.pence == 200000
