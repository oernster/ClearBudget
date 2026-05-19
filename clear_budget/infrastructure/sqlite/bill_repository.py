"""SQLite implementation of BillRepository."""

import sqlite3
from dataclasses import dataclass

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.interfaces.bill_repository import BillRepository
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass
class SQLiteBillRepository:
    """SQLite-backed bill repository."""

    conn: sqlite3.Connection

    def list_active_for_month(self, *, year_month: YearMonth, include_inactive: bool = False) -> list[Bill]:
        """List bills for a given month, applying per-month overrides.

        Args:
            year_month: Month to query
            include_inactive: When True, include deactivated bills (for display)
        """
        cursor = self.conn.cursor()
        active_filter = "" if include_inactive else "AND b.active = 1"
        cursor.execute(
            f"""
            SELECT
                b.id,
                b.name,
                COALESCE(o.amount_pence, b.amount_pence) AS amount_pence,
                COALESCE(o.payment_method_id, b.payment_method_id) AS payment_method_id,
                b.category,
                b.bill_type,
                COALESCE(o.day_of_month, b.day_of_month) AS day_of_month,
                b.target_card_id,
                b.start_year,
                b.start_month,
                b.end_year,
                b.end_month,
                b.active
            FROM bills b
            LEFT JOIN bill_month_overrides o
                ON o.bill_id = b.id AND o.year = ? AND o.month = ?
            WHERE (b.start_year < ? OR (b.start_year = ? AND b.start_month <= ?))
              AND (b.end_year IS NULL OR b.end_year > ? OR
                   (b.end_year = ? AND b.end_month >= ?))
              {active_filter}
            """,
            (
                year_month.year,
                year_month.month,
                year_month.year,
                year_month.year,
                year_month.month,
                year_month.year,
                year_month.year,
                year_month.month,
            ),
        )

        bills = []
        for row in cursor.fetchall():
            bill = Bill(
                id=row["id"],
                name=row["name"],
                amount=Amount(pence=row["amount_pence"]),
                payment_method_id=row["payment_method_id"],
                category=row["category"],
                bill_type=row["bill_type"],
                day_of_month=row["day_of_month"],
                start_ym=YearMonth(row["start_year"], row["start_month"]),
                end_ym=(
                    YearMonth(row["end_year"], row["end_month"])
                    if row["end_year"]
                    else None
                ),
                active=bool(row["active"]),
                target_card_id=row["target_card_id"],
            )
            bills.append(bill)

        return bills

    def set_active(self, *, bill_id: int, active: bool) -> None:
        """Set the active state of a bill."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE bills SET active = ? WHERE id = ?",
            (1 if active else 0, bill_id),
        )
        self.conn.commit()

    def get_by_id(self, *, bill_id: int) -> Bill | None:
        """Get bill by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, amount_pence, payment_method_id, category,
                   bill_type, day_of_month, start_year, start_month,
                   end_year, end_month, active, target_card_id
            FROM bills WHERE id = ?
            """,
            (bill_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return Bill(
            id=row["id"],
            name=row["name"],
            amount=Amount(pence=row["amount_pence"]),
            payment_method_id=row["payment_method_id"],
            category=row["category"],
            bill_type=row["bill_type"],
            day_of_month=row["day_of_month"],
            start_ym=YearMonth(row["start_year"], row["start_month"]),
            end_ym=(
                YearMonth(row["end_year"], row["end_month"])
                if row["end_year"]
                else None
            ),
            active=bool(row["active"]),
            target_card_id=row["target_card_id"],
        )

    def add(self, *, bill: Bill) -> Bill:
        """Add a bill."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO bills
            (name, amount_pence, payment_method_id, category, bill_type,
             day_of_month, start_year, start_month, end_year, end_month, active, target_card_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bill.name, bill.amount.pence, bill.payment_method_id, bill.category,
                bill.bill_type, bill.day_of_month, bill.start_ym.year, bill.start_ym.month,
                bill.end_ym.year if bill.end_ym else None,
                bill.end_ym.month if bill.end_ym else None,
                1 if bill.active else 0, bill.target_card_id,
            ),
        )
        self.conn.commit()
        return Bill(
            id=cursor.lastrowid, name=bill.name, amount=bill.amount,
            payment_method_id=bill.payment_method_id, category=bill.category,
            bill_type=bill.bill_type, day_of_month=bill.day_of_month,
            start_ym=bill.start_ym, end_ym=bill.end_ym, active=bill.active,
            target_card_id=bill.target_card_id,
        )

    def update(self, *, bill: Bill) -> Bill:
        """Update a bill."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE bills
            SET name = ?, amount_pence = ?, payment_method_id = ?,
                category = ?, bill_type = ?, day_of_month = ?,
                start_year = ?, start_month = ?, end_year = ?,
                end_month = ?, active = ?, target_card_id = ?
            WHERE id = ?
            """,
            (
                bill.name, bill.amount.pence, bill.payment_method_id, bill.category,
                bill.bill_type, bill.day_of_month, bill.start_ym.year, bill.start_ym.month,
                bill.end_ym.year if bill.end_ym else None,
                bill.end_ym.month if bill.end_ym else None,
                1 if bill.active else 0, bill.target_card_id, bill.id,
            ),
        )
        self.conn.commit()
        return bill

    def deactivate(self, *, bill_id: int) -> None:
        """Deactivate a bill (soft delete — sets active=0)."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE bills SET active = 0 WHERE id = ?", (bill_id,))
        self.conn.commit()

    def hard_delete(self, *, bill_id: int) -> None:
        """Permanently remove a bill and its overrides from the database."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM bill_month_overrides WHERE bill_id = ?", (bill_id,))
        cursor.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
        self.conn.commit()
