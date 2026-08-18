"""Tests for BudgetService.get_month_gap."""

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from tests.application.fakes import (
    FakeBillRepository,
    FakeIncomeSourceRepository,
    FakePaymentMethodRepository,
)

_MONTH = YearMonth(2026, 10)


def _service() -> BudgetService:
    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    payment_method_repo = FakePaymentMethodRepository()
    return BudgetService(
        bill_repo,
        income_repo,
        payment_method_repo,
        MonthGenerator(bill_repo, income_repo),
    )


def _bill(service, name: str, pence: int, *, method: int = 1) -> None:
    service.bill_repo.add(
        bill=Bill(
            id=0,
            name=name,
            amount=Amount(pence=pence),
            payment_method_id=method,
            category="utilities",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
    )


def _income(service, name: str, pence: int) -> None:
    service.income_repo.add(
        income=IncomeSource(
            id=0,
            name=name,
            amount=Amount(pence=pence),
            is_reliable=True,
            day_of_month=20,
        )
    )


class TestMonthGap:
    def test_a_short_month_names_what_it_needs(self):
        service = _service()
        _income(service, "Universal Credit", 122400)
        _income(service, "Family", 60000)
        _bill(service, "Rent", 249087)
        gap = service.get_month_gap(year_month=_MONTH)
        assert gap.income_pence == 182400
        assert gap.bank_bills_pence == 249087
        assert gap.needed_pence == 66687
        assert not gap.holds_flat

    def test_a_month_that_covers_itself_holds_flat(self):
        service = _service()
        _income(service, "Salary", 300000)
        _bill(service, "Rent", 100000)
        gap = service.get_month_gap(year_month=_MONTH)
        assert gap.holds_flat
        assert gap.needed_pence == -200000

    def test_a_card_bill_does_not_widen_the_bank_gap(self):
        service = _service()
        _income(service, "Salary", 200000)
        _bill(service, "Rent", 150000)
        # Paid from a card, so it never leaves the bank account and cannot be
        # part of what the bank needs to hold flat.
        _bill(service, "Subscription", 50000, method=2)
        gap = service.get_month_gap(year_month=_MONTH)
        assert gap.bank_bills_pence == 150000
        assert gap.needed_pence == -50000

    def test_no_cards_means_no_interest(self):
        service = _service()
        _income(service, "Salary", 200000)
        _bill(service, "Rent", 150000)
        assert service.get_month_gap(year_month=_MONTH).card_interest_pence == 0
