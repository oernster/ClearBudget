"""Tests for SQLiteIncomeSourceRepository."""

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)


class TestSQLiteIncomeSourceAdd:
    """Test adding income sources."""

    def test_add_income_source(self, db) -> None:
        """Test adding an income source."""
        repo = SQLiteIncomeSourceRepository(db.conn)

        income = IncomeSource(
            id=0,
            name="Universal Credit",
            amount=Amount(pence=120000),
            is_reliable=True,
            day_of_month=21,
        )

        added = repo.add(income=income)

        assert added.id > 0
        assert added.name == "Universal Credit"
        assert added.is_reliable

    def test_get_by_id(self, db) -> None:
        """Test retrieving income source by ID."""
        repo = SQLiteIncomeSourceRepository(db.conn)

        income = IncomeSource(
            id=0,
            name="Freelance",
            amount=Amount(pence=50000),
            is_reliable=False,
            day_of_month=None,
        )
        added = repo.add(income=income)

        retrieved = repo.get_by_id(income_id=added.id)

        assert retrieved is not None
        assert retrieved.name == "Freelance"
        assert not retrieved.is_reliable

    def test_get_by_id_not_found(self, db) -> None:
        """Test that get_by_id returns None for nonexistent source."""
        repo = SQLiteIncomeSourceRepository(db.conn)
        result = repo.get_by_id(income_id=999)
        assert result is None


class TestSQLiteIncomeSourceList:
    """Test listing income sources."""

    def test_list_active(self, db) -> None:
        """Test listing active income sources."""
        repo = SQLiteIncomeSourceRepository(db.conn)

        repo.add(
            income=IncomeSource(
                id=0,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )
        repo.add(
            income=IncomeSource(
                id=0,
                name="Freelance",
                amount=Amount(pence=50000),
                is_reliable=False,
                day_of_month=None,
            )
        )

        sources = repo.list_active()

        assert len(sources) == 2
        assert any(s.name == "UC" for s in sources)
        assert any(s.name == "Freelance" for s in sources)

    def test_list_reliable(self, db) -> None:
        """Test listing only reliable income sources."""
        repo = SQLiteIncomeSourceRepository(db.conn)

        repo.add(
            income=IncomeSource(
                id=0,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )
        repo.add(
            income=IncomeSource(
                id=0,
                name="Freelance",
                amount=Amount(pence=50000),
                is_reliable=False,
                day_of_month=None,
            )
        )

        sources = repo.list_reliable()

        assert len(sources) == 1
        assert sources[0].name == "UC"
        assert sources[0].is_reliable

    def test_list_skips_inactive(self, db) -> None:
        """Test that inactive sources are excluded."""
        repo = SQLiteIncomeSourceRepository(db.conn)

        active = repo.add(
            income=IncomeSource(
                id=0,
                name="Active",
                amount=Amount(pence=100000),
                is_reliable=True,
                day_of_month=1,
            )
        )
        inactive = repo.add(
            income=IncomeSource(
                id=0,
                name="Inactive",
                amount=Amount.zero(),
                is_reliable=False,
                day_of_month=None,
                active=False,
            )
        )

        sources = repo.list_active()

        assert len(sources) == 1
        assert sources[0].name == "Active"


class TestSQLiteIncomeSourceUpdate:
    """Test updating income sources."""

    def test_update_income_source(self, db) -> None:
        """Test updating an income source."""
        repo = SQLiteIncomeSourceRepository(db.conn)

        income = repo.add(
            income=IncomeSource(
                id=0,
                name="Original",
                amount=Amount(pence=100000),
                is_reliable=True,
                day_of_month=1,
            )
        )

        updated = IncomeSource(
            id=income.id,
            name="Updated",
            amount=Amount(pence=150000),
            is_reliable=False,
            day_of_month=15,
        )

        repo.update(income=updated)

        retrieved = repo.get_by_id(income_id=income.id)

        assert retrieved.name == "Updated"
        assert retrieved.amount.pence == 150000
        assert not retrieved.is_reliable


class TestSQLiteIncomeSourceDeactivate:
    """Test deactivating income sources."""

    def test_deactivate_income_source(self, db) -> None:
        """Test deactivating an income source."""
        repo = SQLiteIncomeSourceRepository(db.conn)

        income = repo.add(
            income=IncomeSource(
                id=0,
                name="To Deactivate",
                amount=Amount(pence=100000),
                is_reliable=True,
                day_of_month=1,
            )
        )

        assert income.active

        repo.deactivate(income_id=income.id)

        retrieved = repo.get_by_id(income_id=income.id)
        assert retrieved is not None
        assert not retrieved.active

    def test_deactivate_affects_list_active(self, db) -> None:
        """Test that deactivated sources don't appear in list_active."""
        repo = SQLiteIncomeSourceRepository(db.conn)

        income = repo.add(
            income=IncomeSource(
                id=0,
                name="To Deactivate",
                amount=Amount(pence=100000),
                is_reliable=True,
                day_of_month=1,
            )
        )

        repo.deactivate(income_id=income.id)

        active_sources = repo.list_active()
        assert len(active_sources) == 0
        assert not any(s.id == income.id for s in active_sources)
