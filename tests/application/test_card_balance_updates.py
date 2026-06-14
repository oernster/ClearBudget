"""Tests for live card balance + elapsed-date balance update helpers."""

from datetime import date

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services._card_balance_updates import (
    get_live_card_balance,
    save_card_with_today_balance,
)
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from tests.application.fakes import (
    FakeBillRepository,
    FakeIncomeSourceRepository,
    FakePaymentMethodRepository,
)


def _make_service(cards: list[CreditCard] | None = None):
    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    pm_repo = FakePaymentMethodRepository(_cards=cards or [])
    gen = MonthGenerator(bill_repo, income_repo)
    svc = BudgetService(bill_repo, income_repo, pm_repo, gen)
    return svc, bill_repo, pm_repo


def _card(**overrides) -> CreditCard:
    defaults = dict(
        id=2,
        name="TestCard",
        credit_limit=Amount(pence=100000),
        current_balance_used=Amount(pence=10000),
        payment_due_day=22,
    )
    defaults.update(overrides)
    return CreditCard(**defaults)


def _bill(**overrides) -> Bill:
    defaults = dict(
        id=1,
        name="Groceries",
        amount=Amount(pence=1500),
        payment_method_id=2,
        category="groceries",
        bill_type="fixed",
        day_of_month=10,
        start_ym=YearMonth(2000, 1),
        end_ym=None,
    )
    defaults.update(overrides)
    return Bill(**defaults)


class TestGetLiveCardBalance:
    def test_returns_pro_rated_balance(self) -> None:
        today = date.today()
        card = _card()
        svc, bill_repo, _pm_repo = _make_service(cards=[card])
        bill_repo.add(bill=_bill(payment_method_id=card.id, day_of_month=1))

        result = svc.get_live_card_balance(card=card)

        assert result.pence >= card.current_balance_used.pence


class TestUpdateCardBalancesForElapsedDates:
    def test_does_nothing_before_payment_due_day(self) -> None:
        today = date(2026, 6, 10)
        card = _card(payment_due_day=22)
        svc, _bill_repo, pm_repo = _make_service(cards=[card])

        svc.update_card_balances_for_elapsed_dates(today=today)

        updated = pm_repo.get_credit_card_by_id(card_id=card.id)
        assert updated.current_balance_used.pence == 10000
        assert updated.balance_applied_year is None

    def test_applies_once_when_due_day_has_passed(self) -> None:
        today = date(2026, 6, 22)
        card = _card(payment_due_day=22, current_balance_used=Amount(pence=10000))
        svc, bill_repo, pm_repo = _make_service(cards=[card])
        bill_repo.add(
            bill=_bill(
                payment_method_id=card.id, amount=Amount(pence=1500), day_of_month=10
            )
        )

        svc.update_card_balances_for_elapsed_dates(today=today)

        updated = pm_repo.get_credit_card_by_id(card_id=card.id)
        assert updated.current_balance_used.pence == 11500
        assert updated.balance_applied_year == 2026
        assert updated.balance_applied_month == 6

    def test_does_not_double_apply_in_same_month(self) -> None:
        today = date(2026, 6, 22)
        card = _card(payment_due_day=22, current_balance_used=Amount(pence=10000))
        svc, bill_repo, pm_repo = _make_service(cards=[card])
        bill_repo.add(
            bill=_bill(
                payment_method_id=card.id, amount=Amount(pence=1500), day_of_month=10
            )
        )

        svc.update_card_balances_for_elapsed_dates(today=today)
        svc.update_card_balances_for_elapsed_dates(today=today)

        updated = pm_repo.get_credit_card_by_id(card_id=card.id)
        assert updated.current_balance_used.pence == 11500

    def test_default_today_uses_current_date(self) -> None:
        card = _card(payment_due_day=1)
        svc, _bill_repo, pm_repo = _make_service(cards=[card])

        svc.update_card_balances_for_elapsed_dates()

        updated = pm_repo.get_credit_card_by_id(card_id=card.id)
        today = date.today()
        assert updated.balance_applied_year == today.year
        assert updated.balance_applied_month == today.month


def _card_activity_bills() -> list:
    """61.98 of charges (day 8) and a 130.00 payment (day 11) on card id 2."""
    return [
        _bill(payment_method_id=2, amount=Amount(pence=6198), day_of_month=8),
        _bill(
            payment_method_id=1,
            category="credit_payment",
            target_card_id=2,
            amount=Amount(pence=13000),
            day_of_month=11,
        ),
    ]


class TestSaveCardWithTodayBalance:
    def test_new_card_stores_entered_balance_verbatim(self) -> None:
        card = _card(id=0, current_balance_used=Amount(pence=0))
        _svc, _bill_repo, pm_repo = _make_service(cards=[])

        card_id = save_card_with_today_balance(
            pm_repo,
            card=card,
            today_balance_pence=50000,
            today=date(2026, 6, 13),
            is_new=True,
        )

        stored = pm_repo.get_credit_card_by_id(card_id=card_id)
        assert stored.current_balance_used.pence == 50000
        assert stored.balance_applied_year == 2026
        assert stored.balance_applied_month == 6
        assert stored.balance_applied_day == 13

    def test_edit_stores_entered_balance_verbatim_with_day_anchor(self) -> None:
        # The stored figure is exactly what the user typed - no hidden opening.
        card = _card(id=2)
        _svc, _bill_repo, pm_repo = _make_service(cards=[card])

        card_id = save_card_with_today_balance(
            pm_repo,
            card=card,
            today_balance_pence=159200,
            today=date(2026, 6, 13),
            is_new=False,
        )

        stored = pm_repo.get_credit_card_by_id(card_id=card_id)
        assert stored.current_balance_used.pence == 159200
        assert stored.balance_applied_year == 2026
        assert stored.balance_applied_month == 6
        assert stored.balance_applied_day == 13

    def test_saved_balance_reads_back_as_used_on_anchor_day(self) -> None:
        # End to end: save the figure, then the live balance for that day equals
        # exactly what was entered. Current Balance == Used.
        card = _card(id=2, payment_due_day=22)
        svc, bill_repo, pm_repo = _make_service(cards=[card])
        for bill in _card_activity_bills():
            bill_repo.add(bill=bill)
        today = date(2026, 6, 13)

        save_card_with_today_balance(
            pm_repo,
            card=card,
            today_balance_pence=159200,
            today=today,
            is_new=False,
        )

        updated = pm_repo.get_credit_card_by_id(card_id=2)
        live = get_live_card_balance(
            pm_repo, svc.get_month_summary, card=updated, today=today
        )
        assert live.pence == 159200

    def test_service_wrapper_persists_entered_balance(self) -> None:
        card = _card(id=2)
        svc, _bill_repo, pm_repo = _make_service(cards=[card])

        card_id = svc.save_credit_card_today_balance(
            card=card,
            today_balance=Amount(pence=159200),
            is_new=False,
            today=date(2026, 6, 13),
        )

        stored = pm_repo.get_credit_card_by_id(card_id=card_id)
        assert stored.current_balance_used.pence == 159200
        assert stored.balance_applied_day == 13
