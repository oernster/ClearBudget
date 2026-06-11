"""Bill per-month override SQL helpers for BudgetService - extracted for LOC limit."""

from clear_budget.domain.entities.bill import Bill  # pragma: no cover
from clear_budget.domain.value_objects.year_month import YearMonth  # pragma: no cover


def upsert_bill_month_override(
    conn, bill: Bill, year_month: YearMonth
) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO bill_month_overrides (
            bill_id, year, month, amount_pence, payment_method_id, day_of_month
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(bill_id, year, month) DO UPDATE SET
            amount_pence = excluded.amount_pence,
            payment_method_id = excluded.payment_method_id,
            day_of_month = excluded.day_of_month
        """,
        (
            bill.id,
            year_month.year,
            year_month.month,
            bill.amount.pence,
            bill.payment_method_id,
            bill.day_of_month,
        ),
    )
    conn.commit()


def delete_bill_month_override(
    conn, bill_id: int, year_month: YearMonth
) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM bill_month_overrides"
        " WHERE bill_id = ? AND year = ? AND month = ?",
        (bill_id, year_month.year, year_month.month),
    )
    conn.commit()
