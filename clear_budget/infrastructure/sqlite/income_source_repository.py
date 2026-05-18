"""SQLite implementation of IncomeSourceRepository."""

import sqlite3
from dataclasses import dataclass

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.interfaces.income_source_repository import (
    IncomeSourceRepository,
)
from clear_budget.domain.value_objects.amount import Amount


@dataclass
class SQLiteIncomeSourceRepository:
    """SQLite-backed income source repository."""

    conn: sqlite3.Connection

    def list_active(self) -> list[IncomeSource]:
        """List all active income sources."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, amount_pence, is_reliable, day_of_month
            FROM income_sources
            WHERE active = 1
            """
        )

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

    def list_reliable(self) -> list[IncomeSource]:
        """List all reliable (forward-projectable) income sources."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, amount_pence, is_reliable, day_of_month
            FROM income_sources
            WHERE active = 1 AND is_reliable = 1
            """
        )

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
