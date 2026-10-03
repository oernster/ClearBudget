"""A due day stored before the range rule still loads.

The table cell used to write any integer. Now that the entities refuse a day
outside 1 to 31, a row holding one would raise while a month is listed and
take the whole view with it. Every read path therefore repairs the value the
way the overnight update already treated it (see `due_day_from_storage`); the
row itself is left alone until the user next saves it.
"""

import pytest

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.due_day import LAST_DUE_DAY
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)

_MONTH = YearMonth(2026, 4)
_CASES = [(45, LAST_DUE_DAY), (-3, None), (0, None)]


def _store_bill(db, raw_day: int) -> int:
    bill = SQLiteBillRepository(db.conn).add(
        bill=Bill(
            id=0,
            name="Rent",
            amount=Amount(pence=100),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
    )
    db.conn.execute(
        "UPDATE bills SET day_of_month = ? WHERE id = ?", (raw_day, bill.id)
    )
    db.conn.commit()
    return bill.id


def _store_income(db, raw_day: int) -> int:
    income = SQLiteIncomeSourceRepository(db.conn).add(
        income=IncomeSource(
            id=0, name="Pay", amount=Amount(pence=100), is_reliable=True, day_of_month=1
        )
    )
    db.conn.execute(
        "UPDATE income_sources SET day_of_month = ? WHERE id = ?", (raw_day, income.id)
    )
    db.conn.commit()
    return income.id


def _store_extra(db, raw_day: int) -> int:
    extra = SQLiteIncomeSourceRepository(db.conn).add_month_extra(
        income=IncomeSource(
            id=0,
            name="Gift",
            amount=Amount(pence=100),
            is_reliable=True,
            day_of_month=1,
        ),
        year_month=_MONTH,
    )
    db.conn.execute(
        "UPDATE income_month_extras SET day_of_month = ? WHERE id = ?",
        (raw_day, extra.id),
    )
    db.conn.commit()
    return extra.id


@pytest.mark.parametrize(("raw", "day"), _CASES)
class TestEveryReadPathRepairs:
    def test_a_bill_by_id(self, db, raw, day) -> None:
        bill_id = _store_bill(db, raw)
        assert (
            SQLiteBillRepository(db.conn).get_by_id(bill_id=bill_id).day_of_month == day
        )

    def test_a_bill_in_a_month(self, db, raw, day) -> None:
        _store_bill(db, raw)
        (bill,) = SQLiteBillRepository(db.conn).list_active_for_month(year_month=_MONTH)
        assert bill.day_of_month == day

    def test_an_income_by_id(self, db, raw, day) -> None:
        income_id = _store_income(db, raw)
        repo = SQLiteIncomeSourceRepository(db.conn)
        assert repo.get_by_id(income_id=income_id).day_of_month == day

    def test_an_income_in_a_month(self, db, raw, day) -> None:
        _store_income(db, raw)
        repo = SQLiteIncomeSourceRepository(db.conn)
        (income,) = repo.list_active_for_month(year_month=_MONTH)
        assert income.day_of_month == day

    def test_a_one_off_income(self, db, raw, day) -> None:
        _store_extra(db, raw)
        repo = SQLiteIncomeSourceRepository(db.conn)
        (extra,) = repo.list_extras_for_month(year_month=_MONTH)
        assert extra.day_of_month == day
