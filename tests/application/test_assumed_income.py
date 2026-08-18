"""Income marked NOT reliable is money expected rather than money held.

It is excluded from every figure unless asked for; it is always carried
separately as the gap specification: what has to arrive for an assumed
projection to come true.
"""

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
    return BudgetService(
        bill_repo,
        income_repo,
        FakePaymentMethodRepository(),
        MonthGenerator(bill_repo, income_repo),
    )


def _income(service, name: str, pence: int, *, reliable: bool) -> None:
    service.income_repo.add(
        income=IncomeSource(
            id=0,
            name=name,
            amount=Amount(pence=pence),
            is_reliable=reliable,
            day_of_month=10,
        )
    )


def _bill(service, name: str, pence: int) -> None:
    service.bill_repo.add(
        bill=Bill(
            id=0,
            name=name,
            amount=Amount(pence=pence),
            payment_method_id=1,
            category="utilities",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
    )


class TestAssumedIncomeIsExcludedByDefault:
    def test_expected_income_does_not_count_toward_the_total(self):
        service = _service()
        _income(service, "Universal Credit", 122400, reliable=True)
        _income(service, "Expected family top-up", 60000, reliable=False)
        summary = service.get_month_summary(year_month=_MONTH)
        assert summary.total_income.pence == 122400

    def test_expected_income_is_not_among_the_counted_sources(self):
        service = _service()
        _income(service, "Universal Credit", 122400, reliable=True)
        _income(service, "Expected family top-up", 60000, reliable=False)
        summary = service.get_month_summary(year_month=_MONTH)
        assert [i.name for i in summary.income_sources] == ["Universal Credit"]

    def test_expected_income_never_narrows_the_gap(self):
        # The gap says what must be found. Money that might not arrive cannot
        # be what closes it.
        service = _service()
        _income(service, "Universal Credit", 122400, reliable=True)
        _income(service, "Expected family top-up", 60000, reliable=False)
        _bill(service, "Rent", 182400)
        assert service.get_month_gap(year_month=_MONTH).needed_pence == 60000


class TestAssumedIncomeIsCarriedAsTheGapSpecification:
    def test_it_is_listed_whether_or_not_it_was_counted(self):
        service = _service()
        _income(service, "Universal Credit", 122400, reliable=True)
        _income(service, "Expected family top-up", 60000, reliable=False)
        for include in (False, True):
            summary = service.get_month_summary(
                year_month=_MONTH, include_assumed=include
            )
            assert [i.name for i in summary.assumed_income_sources] == [
                "Expected family top-up"
            ]

    def test_a_month_expecting_nothing_lists_nothing(self):
        service = _service()
        _income(service, "Universal Credit", 122400, reliable=True)
        summary = service.get_month_summary(year_month=_MONTH)
        assert summary.assumed_income_sources == ()


class TestAssumedIncomeWhenAskedFor:
    def test_including_it_raises_the_total_by_exactly_that_amount(self):
        service = _service()
        _income(service, "Universal Credit", 122400, reliable=True)
        _income(service, "Expected family top-up", 60000, reliable=False)
        known = service.get_month_summary(year_month=_MONTH)
        probable = service.get_month_summary(year_month=_MONTH, include_assumed=True)
        assert probable.total_income.pence - known.total_income.pence == 60000

    def test_including_it_closes_the_gap_it_is_expected_to_close(self):
        service = _service()
        _income(service, "Universal Credit", 122400, reliable=True)
        _income(service, "Expected family top-up", 60000, reliable=False)
        _bill(service, "Rent", 182400)
        gap = service.get_month_gap(year_month=_MONTH, include_assumed=True)
        assert gap.holds_flat
