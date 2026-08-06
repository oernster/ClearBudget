"""A rent increase, end to end through the repository.

The amount a month reports comes from the bill's scheduled changes, so raising
the rent from a month forward leaves every earlier month reporting what it
actually cost.
"""

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository

_ORIGINAL_RENT = 90_000
_INCREASED_RENT = 100_000
_ONE_OFF = 50_000

_AUGUST = YearMonth(2026, 8)
_SEPTEMBER = YearMonth(2026, 9)
_OCTOBER = YearMonth(2026, 10)


def _add_rent(repo: SQLiteBillRepository) -> Bill:
    return repo.add(
        bill=Bill(
            id=0,
            name="Rent",
            amount=Amount(pence=_ORIGINAL_RENT),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
    )


def _amount_in(repo: SQLiteBillRepository, year_month: YearMonth) -> int:
    bills = repo.list_active_for_month(year_month=year_month)
    assert len(bills) == 1
    return bills[0].amount.pence


class TestRentIncrease:
    def test_the_increase_applies_from_its_month_onward(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        rent = _add_rent(repo)
        repo.add_amount_change(
            bill_id=rent.id,
            year_month=_SEPTEMBER,
            amount=Amount(pence=_INCREASED_RENT),
        )
        assert _amount_in(repo, _SEPTEMBER) == _INCREASED_RENT
        assert _amount_in(repo, _OCTOBER) == _INCREASED_RENT

    def test_an_earlier_month_still_reports_the_old_amount(self, db) -> None:
        """The forward-only rule, through real storage."""
        repo = SQLiteBillRepository(db.conn)
        rent = _add_rent(repo)
        repo.add_amount_change(
            bill_id=rent.id,
            year_month=_SEPTEMBER,
            amount=Amount(pence=_INCREASED_RENT),
        )
        assert _amount_in(repo, _AUGUST) == _ORIGINAL_RENT

    def test_a_bill_with_no_changes_is_unaffected(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        _add_rent(repo)
        assert _amount_in(repo, _OCTOBER) == _ORIGINAL_RENT

    def test_the_change_rides_on_the_bill_that_is_returned(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        rent = _add_rent(repo)
        repo.add_amount_change(
            bill_id=rent.id,
            year_month=_SEPTEMBER,
            amount=Amount(pence=_INCREASED_RENT),
        )
        bills = repo.list_active_for_month(year_month=_OCTOBER)
        assert len(bills[0].amount_changes) == 1


class TestRecordingChanges:
    def test_changes_are_listed_oldest_first(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        rent = _add_rent(repo)
        repo.add_amount_change(
            bill_id=rent.id, year_month=_OCTOBER, amount=Amount(pence=_INCREASED_RENT)
        )
        repo.add_amount_change(
            bill_id=rent.id, year_month=_SEPTEMBER, amount=Amount(pence=_ONE_OFF)
        )
        changes = repo.list_amount_changes(bill_id=rent.id)
        assert [c.sort_key for c in changes] == [(2026, 9), (2026, 10)]

    def test_a_second_change_for_the_same_month_replaces_the_first(self, db) -> None:
        """Two different amounts cannot both start in the same month."""
        repo = SQLiteBillRepository(db.conn)
        rent = _add_rent(repo)
        repo.add_amount_change(
            bill_id=rent.id, year_month=_SEPTEMBER, amount=Amount(pence=_ONE_OFF)
        )
        repo.add_amount_change(
            bill_id=rent.id,
            year_month=_SEPTEMBER,
            amount=Amount(pence=_INCREASED_RENT),
        )
        assert len(repo.list_amount_changes(bill_id=rent.id)) == 1
        assert _amount_in(repo, _SEPTEMBER) == _INCREASED_RENT

    def test_deleting_a_change_restores_the_earlier_amount(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        rent = _add_rent(repo)
        repo.add_amount_change(
            bill_id=rent.id,
            year_month=_SEPTEMBER,
            amount=Amount(pence=_INCREASED_RENT),
        )
        repo.delete_amount_change(bill_id=rent.id, year_month=_SEPTEMBER)
        assert repo.list_amount_changes(bill_id=rent.id) == ()
        assert _amount_in(repo, _SEPTEMBER) == _ORIGINAL_RENT

    def test_a_bill_with_no_changes_lists_none(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        rent = _add_rent(repo)
        assert repo.list_amount_changes(bill_id=rent.id) == ()

    def test_asking_for_no_bills_at_all_queries_nothing(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        assert repo.amount_changes_for_bills(()) == {}


class TestOverridesStillWin:
    def test_a_single_month_override_beats_the_schedule(self, db) -> None:
        """An override says "this one month differed", not "we changed course"."""
        repo = SQLiteBillRepository(db.conn)
        rent = _add_rent(repo)
        repo.add_amount_change(
            bill_id=rent.id,
            year_month=_SEPTEMBER,
            amount=Amount(pence=_INCREASED_RENT),
        )
        db.conn.execute(
            "INSERT INTO bill_month_overrides"
            " (bill_id, year, month, amount_pence, payment_method_id)"
            " VALUES (?, ?, ?, ?, 1)",
            (rent.id, _SEPTEMBER.year, _SEPTEMBER.month, _ONE_OFF),
        )
        db.conn.commit()
        assert _amount_in(repo, _SEPTEMBER) == _ONE_OFF
        # The month after is back on the schedule.
        assert _amount_in(repo, _OCTOBER) == _INCREASED_RENT
