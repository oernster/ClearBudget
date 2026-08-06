"""Storage for a bill's scheduled amount changes.

Split out of `bill_repository.py` to keep it clear of the size cap. One concern:
the rows in `bill_amount_changes`, which say what a bill costs from a given
month onward. Which amount applies to a month is decided in the domain, by
`domain.services.bill_amount_schedule`, never here.
"""

from __future__ import annotations

import sqlite3

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.bill_amount_change import BillAmountChange
from clear_budget.domain.value_objects.year_month import YearMonth


class BillAmountChangesMixin:
    """Scheduled amount changes for SQLiteBillRepository."""

    conn: sqlite3.Connection

    def add_amount_change(
        self, *, bill_id: int, year_month: YearMonth, amount: Amount
    ) -> None:
        """Record what a bill costs from `year_month` onward.

        Recording a second change for a month already carrying one replaces it,
        because two different amounts cannot both start in the same month.
        Earlier months are untouched: that is the whole point of the table.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO bill_amount_changes"
            " (bill_id, effective_year, effective_month, amount_pence)"
            " VALUES (?, ?, ?, ?)",
            (bill_id, year_month.year, year_month.month, amount.pence),
        )
        self.conn.commit()

    def set_amount_changes(
        self, *, bill_id: int, changes: tuple[BillAmountChange, ...]
    ) -> None:
        """Replace every scheduled change for a bill with `changes`.

        The dialog hands back the whole set it is holding, so this is a
        replace rather than a merge; anything the user removed there has to
        disappear here.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM bill_amount_changes WHERE bill_id = ?", (bill_id,))
        cursor.executemany(
            "INSERT INTO bill_amount_changes"
            " (bill_id, effective_year, effective_month, amount_pence)"
            " VALUES (?, ?, ?, ?)",
            [
                (
                    bill_id,
                    c.effective_year,
                    c.effective_month,
                    c.new_amount.pence,
                )
                for c in changes
            ],
        )
        self.conn.commit()

    def delete_amount_change(self, *, bill_id: int, year_month: YearMonth) -> None:
        """Remove the change effective from `year_month`, if there is one."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM bill_amount_changes"
            " WHERE bill_id = ? AND effective_year = ? AND effective_month = ?",
            (bill_id, year_month.year, year_month.month),
        )
        self.conn.commit()

    def list_amount_changes(self, *, bill_id: int) -> tuple[BillAmountChange, ...]:
        """Every scheduled change for one bill, oldest first."""
        return self.amount_changes_for_bills((bill_id,)).get(bill_id, ())

    def amount_changes_for_bills(
        self, bill_ids: tuple[int, ...]
    ) -> dict[int, tuple[BillAmountChange, ...]]:
        """Changes for several bills at once, keyed by bill id.

        One query rather than one per bill, so listing a month does not fan out
        into a query per row.
        """
        if not bill_ids:
            return {}
        placeholders = ",".join("?" for _ in bill_ids)
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT bill_id, effective_year, effective_month, amount_pence"
            f" FROM bill_amount_changes WHERE bill_id IN ({placeholders})"
            " ORDER BY effective_year, effective_month, id",
            bill_ids,
        )
        grouped: dict[int, list[BillAmountChange]] = {}
        for row in cursor.fetchall():
            grouped.setdefault(row["bill_id"], []).append(
                BillAmountChange(
                    effective_year=row["effective_year"],
                    effective_month=row["effective_month"],
                    new_amount=Amount(pence=row["amount_pence"]),
                )
            )
        return {bill_id: tuple(changes) for bill_id, changes in grouped.items()}
