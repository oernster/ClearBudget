"""Tests for SQLiteBillRepository."""

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import (
    SQLiteBillRepository,
)


class TestSQLiteBillRepositoryAdd:
    """Test adding bills."""

    def test_add_bill(self, db) -> None:
        """Test adding a bill."""
        repo = SQLiteBillRepository(db.conn)

        bill = Bill(
            id=0,
            name="Rent",
            amount=Amount(pence=135000),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )

        added = repo.add(bill=bill)

        assert added.id > 0
        assert added.name == "Rent"
        assert added.amount.pence == 135000

    def test_get_by_id(self, db) -> None:
        """Test retrieving bill by ID."""
        repo = SQLiteBillRepository(db.conn)

        bill = Bill(
            id=0,
            name="Utilities",
            amount=Amount(pence=5000),
            payment_method_id=1,
            category="utilities",
            bill_type="fixed",
            day_of_month=15,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
        added = repo.add(bill=bill)

        retrieved = repo.get_by_id(bill_id=added.id)

        assert retrieved is not None
        assert retrieved.name == "Utilities"
        assert retrieved.id == added.id

    def test_get_by_id_not_found(self, db) -> None:
        """Test that get_by_id returns None for nonexistent bill."""
        repo = SQLiteBillRepository(db.conn)
        result = repo.get_by_id(bill_id=999)
        assert result is None


class TestSQLiteBillRepositoryListActive:
    """Test listing active bills for a month."""

    def test_list_active_for_month(self, db) -> None:
        """Test listing active bills for a specific month."""
        repo = SQLiteBillRepository(db.conn)

        # Add perpetual bill
        repo.add(
            bill=Bill(
                id=0,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )

        bills = repo.list_active_for_month(year_month=YearMonth(2026, 6))

        assert len(bills) == 1
        assert bills[0].name == "Rent"

    def test_list_respects_start_date(self, db) -> None:
        """Test that bills before start_ym aren't included."""
        repo = SQLiteBillRepository(db.conn)

        repo.add(
            bill=Bill(
                id=0,
                name="Future",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 6),
                end_ym=None,
            )
        )

        # May (before June start)
        bills_may = repo.list_active_for_month(year_month=YearMonth(2026, 5))
        assert len(bills_may) == 0

        # June (at start)
        bills_june = repo.list_active_for_month(year_month=YearMonth(2026, 6))
        assert len(bills_june) == 1

    def test_list_respects_end_date(self, db) -> None:
        """Test that bills after end_ym aren't included."""
        repo = SQLiteBillRepository(db.conn)

        repo.add(
            bill=Bill(
                id=0,
                name="Temporary",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="discretionary",
                bill_type="expiring",
                day_of_month=1,
                start_ym=YearMonth(2026, 6),
                end_ym=YearMonth(2026, 6),
            )
        )

        # June (includes)
        bills_june = repo.list_active_for_month(year_month=YearMonth(2026, 6))
        assert len(bills_june) == 1

        # July (excludes)
        bills_july = repo.list_active_for_month(year_month=YearMonth(2026, 7))
        assert len(bills_july) == 0

    def test_list_respects_active_flag(self, db) -> None:
        """Test that inactive bills aren't included."""
        repo = SQLiteBillRepository(db.conn)

        bill = repo.add(
            bill=Bill(
                id=0,
                name="Active",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )

        # Initially included
        bills = repo.list_active_for_month(year_month=YearMonth(2026, 6))
        assert len(bills) == 1

        # Deactivate
        repo.deactivate(bill_id=bill.id)

        # Now excluded
        bills = repo.list_active_for_month(year_month=YearMonth(2026, 6))
        assert len(bills) == 0


class TestSQLiteBillRepositoryUpdate:
    """Test updating bills."""

    def test_update_bill(self, db) -> None:
        """Test updating a bill."""
        repo = SQLiteBillRepository(db.conn)

        bill = repo.add(
            bill=Bill(
                id=0,
                name="Original",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )

        updated_bill = Bill(
            id=bill.id,
            name="Updated",
            amount=Amount(pence=150000),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )

        repo.update(bill=updated_bill)

        retrieved = repo.get_by_id(bill_id=bill.id)

        assert retrieved.name == "Updated"
        assert retrieved.amount.pence == 150000
