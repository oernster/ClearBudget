"""Income per-month override SQL helpers for BudgetService - extracted for LOC limit."""

from clear_budget.domain.entities.income_source import IncomeSource  # pragma: no cover
from clear_budget.domain.value_objects.year_month import YearMonth  # pragma: no cover


def upsert_income_month_override(
    conn, income: IncomeSource, year_month: YearMonth
) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO income_month_overrides (
            income_id, year, month, amount_pence, day_of_month
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(income_id, year, month) DO UPDATE SET
            amount_pence = excluded.amount_pence,
            day_of_month = excluded.day_of_month
        """,
        (
            income.id,
            year_month.year,
            year_month.month,
            income.amount.pence,
            income.day_of_month,
        ),
    )
    conn.commit()


def delete_income_month_override(
    conn, income_id: int, year_month: YearMonth
) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM income_month_overrides"
        " WHERE income_id = ? AND year = ? AND month = ?",
        (income_id, year_month.year, year_month.month),
    )
    conn.commit()
