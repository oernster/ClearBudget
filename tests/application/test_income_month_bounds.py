"""An income that stops names its final month; it is never erased.

Income used to have no start and no end, so it appeared in every month that
had ever existed and every month that ever would. The only way to record a
stopped income was to delete it, which removed it from the months it really
did arrive in. A bill has carried start_ym and end_ym all along, so this is
the missing half of a pair rather than a new idea.

Both bounds are nullable and a NULL reads as unbounded on that side, so a
database written before the columns existed behaves exactly as it did.
"""

from datetime import date

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.entities.bill import Bill
from clear_budget.application.services.month_generator import MonthGenerator
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

_MAY = YearMonth(2026, 5)
_JUNE = YearMonth(2026, 6)
_JULY = YearMonth(2026, 7)
_AUGUST = YearMonth(2026, 8)


@pytest.fixture()
def service(tmp_path):
    """BudgetService wired to a temp SQLite database."""
    db = Database(tmp_path / "test.db")
    db.connect()
    db.create_schema()
    svc = BudgetService(
        bill_repo=SQLiteBillRepository(db.conn),
        income_repo=SQLiteIncomeSourceRepository(db.conn),
        payment_method_repo=SQLitePaymentMethodRepository(db.conn),
        month_generator=MonthGenerator(
            SQLiteBillRepository(db.conn), SQLiteIncomeSourceRepository(db.conn)
        ),
    )
    yield svc
    db.close()


def _income(name="Salary", *, start=None, end=None) -> IncomeSource:
    return IncomeSource(
        id=0,
        name=name,
        amount=Amount(pence=100000),
        is_reliable=True,
        day_of_month=10,
        start_ym=start,
        end_ym=end,
    )


def _bill(name="Rent", pence=50000, day=5) -> Bill:
    return Bill(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        payment_method_id=1,
        category="utilities",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
        target_card_id=None,
    )


def _seed_balance(conn, *, pence: int, iso: str) -> None:
    for key, value in (
        ("bank_balance", str(pence)),
        ("bank_balance_day", str(date.fromisoformat(iso).day)),
        ("bank_balance_date", iso),
    ):
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()


def _names(service, month) -> list[str]:
    return [i.name for i in service.get_month_summary(year_month=month).income_sources]


class TestUnboundedIsUnchanged:
    def test_an_income_stating_neither_bound_appears_in_every_month(self, service):
        service.add_income(income=_income())
        for month in (_MAY, _JUNE, _JULY, _AUGUST):
            assert _names(service, month) == ["Salary"]

    def test_the_bounds_round_trip_as_none(self, service):
        persisted = service.add_income(income=_income())
        fetched = service.income_repo.get_by_id(income_id=persisted.id)
        assert fetched.start_ym is None
        assert fetched.end_ym is None


class TestAnEndMonth:
    def test_the_income_appears_up_to_and_including_its_final_month(self, service):
        service.add_income(income=_income(end=_JUNE))
        assert _names(service, _MAY) == ["Salary"]
        assert _names(service, _JUNE) == ["Salary"]

    def test_it_is_gone_from_every_month_after(self, service):
        service.add_income(income=_income(end=_JUNE))
        assert _names(service, _JULY) == []
        assert _names(service, _AUGUST) == []

    def test_the_end_month_round_trips(self, service):
        persisted = service.add_income(income=_income(end=_JUNE))
        fetched = service.income_repo.get_by_id(income_id=persisted.id)
        assert fetched.end_ym == _JUNE


class TestAStartMonth:
    def test_the_income_is_absent_before_it_began(self, service):
        service.add_income(income=_income(start=_JULY))
        assert _names(service, _MAY) == []
        assert _names(service, _JUNE) == []

    def test_it_appears_from_its_first_month_onward(self, service):
        service.add_income(income=_income(start=_JULY))
        assert _names(service, _JULY) == ["Salary"]
        assert _names(service, _AUGUST) == ["Salary"]

    def test_both_bounds_together_confine_it_to_a_span(self, service):
        service.add_income(income=_income(start=_JUNE, end=_JULY))
        assert _names(service, _MAY) == []
        assert _names(service, _JUNE) == ["Salary"]
        assert _names(service, _JULY) == ["Salary"]
        assert _names(service, _AUGUST) == []


class TestEndingRatherThanDeleting:
    def test_ending_an_income_leaves_earlier_months_untouched(self, service):
        """The whole point: a stopped income keeps the months it arrived in."""
        persisted = service.add_income(income=_income())
        service.end_income(income_id=persisted.id, last_active_month=_JUNE)
        assert _names(service, _MAY) == ["Salary"]
        assert _names(service, _JUNE) == ["Salary"]
        assert _names(service, _JULY) == []

    def test_deleting_still_removes_it_from_history(self, service):
        """Kept deliberately, as the explicit "this was never real" action."""
        persisted = service.add_income(income=_income())
        service.delete_income(income_id=persisted.id)
        assert _names(service, _MAY) == []
        assert _names(service, _JULY) == []

    def test_ending_an_income_that_is_gone_is_not_an_error(self, service):
        service.end_income(income_id=999, last_active_month=_JUNE)
        assert _names(service, _JUNE) == []

    def test_an_edit_after_ending_keeps_the_end_month(self, service):
        persisted = service.add_income(income=_income())
        service.end_income(income_id=persisted.id, last_active_month=_JUNE)
        ended = service.income_repo.get_by_id(income_id=persisted.id)
        service.update_income(income=ended)
        assert _names(service, _JULY) == []


class TestTheEntityRule:
    def test_an_inactive_income_appears_in_no_month_whatever_its_bounds(self):
        income = IncomeSource(
            id=1,
            name="Salary",
            amount=Amount(pence=1),
            is_reliable=True,
            day_of_month=1,
            active=False,
        )
        assert income.is_active_in_month(_JUNE) is False

    def test_an_unbounded_income_is_active_in_any_month(self):
        assert _income().is_active_in_month(_MAY) is True

    def test_the_bounds_are_inclusive_at_both_edges(self):
        income = _income(start=_JUNE, end=_JULY)
        assert income.is_active_in_month(_MAY) is False
        assert income.is_active_in_month(_JUNE) is True
        assert income.is_active_in_month(_JULY) is True
        assert income.is_active_in_month(_AUGUST) is False


class TestTheProjectionHonoursTheEnd:
    def test_a_month_after_the_end_no_longer_counts_the_income(self, service):
        persisted = service.add_income(income=_income())
        before = service.get_month_summary(year_month=_AUGUST).total_income.pence
        service.end_income(income_id=persisted.id, last_active_month=_JUNE)
        after = service.get_month_summary(year_month=_AUGUST).total_income.pence
        assert before == 100000
        assert after == 0

    def test_the_spendable_figure_reads_the_ended_income(self, service):
        """A bill every month is what makes the two readings diverge.

        Without one the window's low point sits before the income arrives in
        the very first month, so it is the same figure either way and the test
        would pass while proving nothing.
        """
        today = date(2026, 6, 1)
        _seed_balance(service.bill_repo.conn, pence=20000, iso="2026-06-01")
        service.set_safe_to_spend_floor(amount=Amount(pence=0))
        service.add_bill(bill=_bill())
        persisted = service.add_income(income=_income())
        with_income = service.get_safe_to_spend(today=today).amount_pence
        service.end_income(income_id=persisted.id, last_active_month=_JUNE)
        without = service.get_safe_to_spend(today=today).amount_pence
        assert without < with_income
