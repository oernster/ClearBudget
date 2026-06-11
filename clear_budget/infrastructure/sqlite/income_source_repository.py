"""SQLite implementation of IncomeSourceRepository."""

import sqlite3
from dataclasses import dataclass

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass
class SQLiteIncomeSourceRepository:
    """SQLite-backed income source repository."""

    conn: sqlite3.Connection

    def list_active(self) -> list[IncomeSource]:
        """List all active income sources."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, name, amount_pence, is_reliable, day_of_month
            FROM income_sources
            WHERE active = 1
            """)

        sources = []
        for row in cursor.fetchall():
            source = IncomeSource(
                id=row["id"],
                name=row["name"],
                amount=Amount(pence=row["amount_pence"]),
                is_reliable=bool(row["is_reliable"]),
                day_of_month=row["day_of_month"],
            )
            sources.append(source)

        return sources

    def list_all(self) -> list[IncomeSource]:
        """List all income sources including inactive."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, name, amount_pence, is_reliable, day_of_month, active
            FROM income_sources
            """)
        return [
            IncomeSource(
                id=row["id"],
                name=row["name"],
                amount=Amount(pence=row["amount_pence"]),
                is_reliable=bool(row["is_reliable"]),
                day_of_month=row["day_of_month"],
                active=bool(row["active"]),
            )
            for row in cursor.fetchall()
        ]

    def list_reliable(self) -> list[IncomeSource]:
        """List all reliable (forward-projectable) income sources."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, name, amount_pence, is_reliable, day_of_month
            FROM income_sources
            WHERE active = 1 AND is_reliable = 1
            """)

        sources = []
        for row in cursor.fetchall():
            source = IncomeSource(
                id=row["id"],
                name=row["name"],
                amount=Amount(pence=row["amount_pence"]),
                is_reliable=True,
                day_of_month=row["day_of_month"],
            )
            sources.append(source)

        return sources

    def get_by_id(self, *, income_id: int) -> IncomeSource | None:
        """Get income source by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, amount_pence, is_reliable, day_of_month, active
            FROM income_sources WHERE id = ?
            """,
            (income_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return IncomeSource(
            id=row["id"],
            name=row["name"],
            amount=Amount(pence=row["amount_pence"]),
            is_reliable=bool(row["is_reliable"]),
            day_of_month=row["day_of_month"],
            active=bool(row["active"]),
        )

    def add(self, *, income: IncomeSource) -> IncomeSource:
        """Add an income source."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO income_sources
            (name, amount_pence, is_reliable, day_of_month, active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                income.name,
                income.amount.pence,
                1 if income.is_reliable else 0,
                income.day_of_month,
                1 if income.active else 0,
            ),
        )
        self.conn.commit()

        return IncomeSource(
            id=cursor.lastrowid,
            name=income.name,
            amount=income.amount,
            is_reliable=income.is_reliable,
            day_of_month=income.day_of_month,
            active=income.active,
        )

    def update(self, *, income: IncomeSource) -> IncomeSource:
        """Update an income source."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE income_sources
            SET name = ?, amount_pence = ?, is_reliable = ?,
                day_of_month = ?, active = ?
            WHERE id = ?
            """,
            (
                income.name,
                income.amount.pence,
                1 if income.is_reliable else 0,
                income.day_of_month,
                1 if income.active else 0,
                income.id,
            ),
        )
        self.conn.commit()
        return income

    def deactivate(self, *, income_id: int) -> None:
        """Deactivate an income source."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE income_sources SET active = 0 WHERE id = ?", (income_id,)
        )
        self.conn.commit()

    def hard_delete(self, *, income_id: int) -> None:
        """Permanently remove an income source from the database."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM income_month_overrides WHERE income_id = ?", (income_id,)
        )
        cursor.execute(
            "DELETE FROM income_month_skips WHERE income_id = ?", (income_id,)
        )
        cursor.execute(
            "DELETE FROM income_month_received WHERE income_id = ?", (income_id,)
        )
        cursor.execute("DELETE FROM income_sources WHERE id = ?", (income_id,))
        self.conn.commit()

    def list_active_for_month(
        self, *, year_month: YearMonth, include_inactive: bool = False
    ) -> list[IncomeSource]:
        """List income sources for a given month, applying per-month overrides.

        Args:
            year_month: Month to query
            include_inactive: When True, include deactivated and skipped income
        """
        cursor = self.conn.cursor()
        active_filter = "" if include_inactive else "AND i.active = 1"
        skip_filter = "" if include_inactive else "AND s.income_id IS NULL"
        cursor.execute(
            f"""
            SELECT
                i.id,
                i.name,
                COALESCE(o.amount_pence, i.amount_pence) AS amount_pence,
                i.is_reliable,
                COALESCE(o.day_of_month, i.day_of_month) AS day_of_month,
                i.active,
                CASE WHEN s.income_id IS NOT NULL THEN 1 ELSE 0
                    END AS skipped_for_month,
                CASE WHEN o.income_id IS NOT NULL THEN 1 ELSE 0
                    END AS has_month_override,
                CASE WHEN r.income_id IS NOT NULL THEN 1 ELSE 0
                    END AS received_for_month
            FROM income_sources i
            LEFT JOIN income_month_overrides o
                ON o.income_id = i.id AND o.year = ? AND o.month = ?
            LEFT JOIN income_month_skips s
                ON s.income_id = i.id AND s.year = ? AND s.month = ?
            LEFT JOIN income_month_received r
                ON r.income_id = i.id AND r.year = ? AND r.month = ?
            WHERE 1=1
              {active_filter}
              {skip_filter}
            """,
            (
                year_month.year,
                year_month.month,
                year_month.year,
                year_month.month,
                year_month.year,
                year_month.month,
            ),
        )
        return [
            IncomeSource(
                id=row["id"],
                name=row["name"],
                amount=Amount(pence=row["amount_pence"]),
                is_reliable=bool(row["is_reliable"]),
                day_of_month=row["day_of_month"],
                active=bool(row["active"]),
                skipped_for_month=bool(row["skipped_for_month"]),
                has_month_override=bool(row["has_month_override"]),
                received_for_month=bool(row["received_for_month"]),
            )
            for row in cursor.fetchall()
        ]

    def skip_for_month(self, *, income_id: int, year_month: YearMonth) -> None:
        """Mark an income source as skipped for one specific month."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO income_month_skips"
            " (income_id, year, month) VALUES (?, ?, ?)",
            (income_id, year_month.year, year_month.month),
        )
        self.conn.commit()

    def unskip_for_month(self, *, income_id: int, year_month: YearMonth) -> None:
        """Remove a month-skip for an income source."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM income_month_skips"
            " WHERE income_id = ? AND year = ? AND month = ?",
            (income_id, year_month.year, year_month.month),
        )
        self.conn.commit()

    def mark_received_for_month(self, *, income_id: int, year_month: YearMonth) -> None:
        """Mark an income source as received for one specific month."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO income_month_received"
            " (income_id, year, month) VALUES (?, ?, ?)",
            (income_id, year_month.year, year_month.month),
        )
        self.conn.commit()

    def unmark_received_for_month(
        self, *, income_id: int, year_month: YearMonth
    ) -> None:
        """Remove the received flag for an income source in one specific month."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM income_month_received"
            " WHERE income_id = ? AND year = ? AND month = ?",
            (income_id, year_month.year, year_month.month),
        )
        self.conn.commit()

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
