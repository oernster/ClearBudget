"""Per-month bill state in SQLiteBillRepository: skip, active and paid.

Split out of test_sqlite_bill_repository.py, which was at 384 lines and so one
edit away from failing the size cap. These three concerns share a shape: each
records a fact about a bill in one month without altering the bill itself.
"""

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import (
    SQLiteBillRepository,
)


class TestSQLiteBillRepositorySkipForMonth:
    """Test skip_for_month and unskip_for_month."""

    def test_skip_for_month_excludes_bill(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        bill = repo.add(
            bill=Bill(
                id=0,
                name="SkipMe",
                amount=Amount(pence=1000),
                payment_method_id=1,
                category="groceries",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        ym = YearMonth(2026, 6)

        repo.skip_for_month(bill_id=bill.id, year_month=ym)

        active = repo.list_active_for_month(year_month=ym)
        assert not any(b.id == bill.id for b in active)

    def test_unskip_for_month_restores_bill(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        bill = repo.add(
            bill=Bill(
                id=0,
                name="Restored",
                amount=Amount(pence=1000),
                payment_method_id=1,
                category="groceries",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        ym = YearMonth(2026, 6)

        repo.skip_for_month(bill_id=bill.id, year_month=ym)
        repo.unskip_for_month(bill_id=bill.id, year_month=ym)

        active = repo.list_active_for_month(year_month=ym)
        assert any(b.id == bill.id for b in active)


class TestSQLiteBillRepositorySetActive:
    """Test set_active method."""

    def test_set_active_false_excludes_from_active_list(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        bill = repo.add(
            bill=Bill(
                id=0,
                name="Test",
                amount=Amount(pence=1000),
                payment_method_id=1,
                category="groceries",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )

        repo.set_active(bill_id=bill.id, active=False)

        active = repo.list_active_for_month(year_month=YearMonth(2026, 5))
        assert not any(b.id == bill.id for b in active)

    def test_set_active_true_restores_bill(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        bill = repo.add(
            bill=Bill(
                id=0,
                name="Restored",
                amount=Amount(pence=500),
                payment_method_id=1,
                category="groceries",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        repo.set_active(bill_id=bill.id, active=False)
        repo.set_active(bill_id=bill.id, active=True)

        active = repo.list_active_for_month(year_month=YearMonth(2026, 5))
        assert any(b.id == bill.id for b in active)


class TestSQLiteBillRepositoryPaidForMonth:
    """Test mark_paid_for_month and unmark_paid_for_month."""

    def test_mark_paid_for_month(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        bill = repo.add(
            bill=Bill(
                id=0,
                name="Rent",
                amount=Amount(pence=1000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        ym = YearMonth(2026, 6)

        repo.mark_paid_for_month(bill_id=bill.id, year_month=ym)

        active = repo.list_active_for_month(year_month=ym)
        marked = next(b for b in active if b.id == bill.id)
        assert marked.paid_for_month is True

    def test_unmark_paid_for_month(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        bill = repo.add(
            bill=Bill(
                id=0,
                name="Rent",
                amount=Amount(pence=1000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        ym = YearMonth(2026, 6)

        repo.mark_paid_for_month(bill_id=bill.id, year_month=ym)
        repo.unmark_paid_for_month(bill_id=bill.id, year_month=ym)

        active = repo.list_active_for_month(year_month=ym)
        marked = next(b for b in active if b.id == bill.id)
        assert marked.paid_for_month is False
