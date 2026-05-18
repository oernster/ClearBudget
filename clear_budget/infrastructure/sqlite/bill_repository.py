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

    def list_active_for_month(self, *, year_month: YearMonth) -> list[Bill]:
        """List active bills for a given month."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, amount_pence, payment_method_id, category,
                   bill_type, day_of_month, start_year, start_month,
                   end_year, end_month
            FROM bills
            WHERE active = 1
              AND (start_year < ? OR (start_year = ? AND start_month <= ?))
              AND (end_year IS NULL OR end_year > ? OR
                   (end_year = ? AND end_month >= ?))
            """,
            (
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
            )
            bills.append(bill)

        return bills

    def get_by_id(self, *, bill_id: int) -> Bill | None:
        """Get bill by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, amount_pence, payment_method_id, category,
                   bill_type, day_of_month, start_year, start_month,
                   end_year, end_month, active
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
        )

    def add(self, *, bill: Bill) -> Bill:
        """Add a bill."""
        print(f"\n[BILL_REPO] add() called with bill: name='{bill.name}', payment_method_id={bill.payment_method_id}")
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO bills
            (name, amount_pence, payment_method_id, category, bill_type,
             day_of_month, start_year, start_month, end_year, end_month, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bill.name,
                bill.amount.pence,
                bill.payment_method_id,
                bill.category,
                bill.bill_type,
                bill.day_of_month,
                bill.start_ym.year,
                bill.start_ym.month,
                bill.end_ym.year if bill.end_ym else None,
                bill.end_ym.month if bill.end_ym else None,
                1 if bill.active else 0,
            ),
        )
        self.conn.commit()
        print(f"[BILL_REPO] INSERT successful, lastrowid={cursor.lastrowid}")

        result = Bill(
            id=cursor.lastrowid,
            name=bill.name,
            amount=bill.amount,
            payment_method_id=bill.payment_method_id,
            category=bill.category,
            bill_type=bill.bill_type,
            day_of_month=bill.day_of_month,
            start_ym=bill.start_ym,
            end_ym=bill.end_ym,
            active=bill.active,
        )
        print(f"[BILL_REPO] Returning bill with payment_method_id={result.payment_method_id}")
        return result

    def update(self, *, bill: Bill) -> Bill:
        """Update a bill."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE bills
            SET name = ?, amount_pence = ?, payment_method_id = ?,
                category = ?, bill_type = ?, day_of_month = ?,
                start_year = ?, start_month = ?, end_year = ?,
                end_month = ?, active = ?
            WHERE id = ?
            """,
            (
                bill.name,
                bill.amount.pence,
                bill.payment_method_id,
                bill.category,
                bill.bill_type,
                bill.day_of_month,
                bill.start_ym.year,
                bill.start_ym.month,
                bill.end_ym.year if bill.end_ym else None,
                bill.end_ym.month if bill.end_ym else None,
                1 if bill.active else 0,
                bill.id,
            ),
        )
        self.conn.commit()
        return bill

    def deactivate(self, *, bill_id: int) -> None:
        """Deactivate a bill."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE bills SET active = 0 WHERE id = ?", (bill_id,))
        self.conn.commit()
