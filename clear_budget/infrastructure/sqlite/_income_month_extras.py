"""One-off income rows scoped to a single month.

Split out of `income_source_repository.py`, which was at 382 lines and so one
edit away from failing the size cap. These rows live in `income_month_extras`
and are not tied to an income_sources template, which makes them a distinct
concern from the template CRUD the repository otherwise holds.
"""

import sqlite3

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


class IncomeMonthExtrasMixin:
    """Month-scoped one-off income for SQLiteIncomeSourceRepository."""

    conn: sqlite3.Connection

    def mark_extra_received(self, *, extra_id: int) -> None:
        """Mark a one-off income entry as received."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE income_month_extras SET received = 1 WHERE id = ?", (extra_id,)
        )
        self.conn.commit()

    def unmark_extra_received(self, *, extra_id: int) -> None:
        """Remove the received flag from a one-off income entry."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE income_month_extras SET received = 0 WHERE id = ?", (extra_id,)
        )
        self.conn.commit()

    def add_month_extra(
        self, *, year_month: YearMonth, income: IncomeSource
    ) -> IncomeSource:
        """Add a one-off income entry scoped to a single month."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO income_month_extras
            (year, month, name, amount_pence, day_of_month, is_reliable)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                year_month.year,
                year_month.month,
                income.name,
                income.amount.pence,
                income.day_of_month,
                1 if income.is_reliable else 0,
            ),
        )
        self.conn.commit()

        return IncomeSource(
            id=cursor.lastrowid,
            name=income.name,
            amount=income.amount,
            is_reliable=income.is_reliable,
            day_of_month=income.day_of_month,
            active=True,
            is_month_only=True,
        )

    def list_extras_for_month(self, *, year_month: YearMonth) -> list[IncomeSource]:
        """List one-off income entries scoped to the given month."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, amount_pence, day_of_month, is_reliable, received
            FROM income_month_extras
            WHERE year = ? AND month = ?
            """,
            (year_month.year, year_month.month),
        )
        return [
            IncomeSource(
                id=row["id"],
                name=row["name"],
                amount=Amount(pence=row["amount_pence"]),
                is_reliable=bool(row["is_reliable"]),
                day_of_month=row["day_of_month"],
                active=True,
                is_month_only=True,
                received_for_month=bool(row["received"]),
            )
            for row in cursor.fetchall()
        ]

    def update_month_extra(
        self, *, year_month: YearMonth, income: IncomeSource
    ) -> IncomeSource:
        """Update a one-off income entry for the given month."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE income_month_extras
            SET name = ?, amount_pence = ?, day_of_month = ?, is_reliable = ?
            WHERE id = ? AND year = ? AND month = ?
            """,
            (
                income.name,
                income.amount.pence,
                income.day_of_month,
                1 if income.is_reliable else 0,
                income.id,
                year_month.year,
                year_month.month,
            ),
        )
        self.conn.commit()
        return income

    def delete_month_extra(self, *, extra_id: int) -> None:
        """Permanently remove a one-off income entry."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM income_month_extras WHERE id = ?", (extra_id,))
        self.conn.commit()
