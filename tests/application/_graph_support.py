"""Dates and builders shared by the month graph and solvency tests."""

from datetime import date

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth

_TODAY = date(2026, 7, 26)
_JULY = YearMonth(2026, 7)
_AUGUST = YearMonth(2026, 8)
_SEPTEMBER = YearMonth(2026, 9)
_OCTOBER = YearMonth(2026, 10)


def _bill(
    name: str,
    pence: int,
    day,
    *,
    method: int = 1,
    start: YearMonth | None = None,
    category: str = "utilities",
    target_card_id: int | None = None,
) -> Bill:
    return Bill(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        payment_method_id=method,
        category=category,
        bill_type="fixed",
        day_of_month=day,
        start_ym=start or YearMonth(2026, 1),
        end_ym=None,
        target_card_id=target_card_id,
    )


def _income(name: str, pence: int, day) -> IncomeSource:
    return IncomeSource(
        id=0, name=name, amount=Amount(pence=pence), is_reliable=True, day_of_month=day
    )


def _seed_balance(conn, *, pence: int, iso: str) -> None:
    day = date.fromisoformat(iso).day
    for key, value in (
        ("bank_balance", str(pence)),
        ("bank_balance_day", str(day)),
        ("bank_balance_date", iso),
    ):
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()
