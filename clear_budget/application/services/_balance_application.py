"""Balance application log - records and reverses automatic balance changes.

Every amount the app applies to the bank balance automatically (the midnight
fold or the same-day "update balance now?" prompt) is logged per item and
month. Deleting an item then hands its applied amounts back; ending a bill
from a month onward hands back only the months being removed. Setting the
balance by hand clears the log: the typed figure already reflects everything
applied before it, so those applications are no longer reversible.
"""

from clear_budget.application.services._settings_operations import (
    get_bank_balance_pence,
    set_bank_balance_pence,
)
from clear_budget.domain.value_objects.year_month import YearMonth


def record_applied(
    conn, *, item_type: str, item_id: int, year_month: YearMonth, amount_pence: int
) -> None:
    """Log a signed amount applied to the balance for one item in one month."""
    conn.execute(
        "INSERT INTO balance_applied (item_type, item_id, year, month, amount_pence)"
        " VALUES (?, ?, ?, ?, ?)",
        (item_type, item_id, year_month.year, year_month.month, amount_pence),
    )
    conn.commit()


def clear_applied_log(conn) -> None:
    """Drop every logged application (the manual balance entry supersedes them)."""
    conn.execute("DELETE FROM balance_applied")
    conn.commit()


def reverse_applied_for_item(
    conn, *, item_type: str, item_id: int, after: YearMonth | None = None
) -> int:
    """Hand an item's applied amounts back to the balance; return the delta.

    Removes the item's log entries (only those in months after ``after`` when
    given) and applies the opposite of their sum to the stored balance. The
    returned delta is the signed pence handed back (positive for a deleted
    bill, negative for a deleted income); zero when nothing was logged.
    """
    if conn is None:
        return 0
    where = "item_type = ? AND item_id = ?"
    params: list = [item_type, item_id]
    if after is not None:
        where += " AND (year > ? OR (year = ? AND month > ?))"
        params += [after.year, after.year, after.month]
    row = conn.execute(
        f"SELECT COALESCE(SUM(amount_pence), 0) AS total"
        f" FROM balance_applied WHERE {where}",
        params,
    ).fetchone()
    applied = int(row["total"])
    conn.execute(f"DELETE FROM balance_applied WHERE {where}", params)
    if applied == 0:
        conn.commit()
        return 0
    set_bank_balance_pence(conn, get_bank_balance_pence(conn) - applied)
    return -applied


class BalanceApplicationMixin:
    """Same-day balance application operations for BudgetService."""

    __slots__ = ()

    def apply_bill_to_balance_now(self, *, bill, year_month: YearMonth) -> None:
        """Deduct a bill from the balance, mark it paid and log the application."""
        self.adjust_bank_balance(delta_pence=-bill.amount.pence)
        self.mark_bill_paid_for_month(bill_id=bill.id, year_month=year_month)
        record_applied(
            self.bill_repo.conn,
            item_type="bill",
            item_id=bill.id,
            year_month=year_month,
            amount_pence=-bill.amount.pence,
        )

    def apply_income_to_balance_now(self, *, income, year_month: YearMonth) -> None:
        """Add an income to the balance, mark it received and log the application."""
        self.adjust_bank_balance(delta_pence=income.amount.pence)
        if income.is_month_only:
            self.mark_income_extra_received(extra_id=income.id)
            item_type = "income_extra"
        else:
            self.mark_income_received_for_month(
                income_id=income.id, year_month=year_month
            )
            item_type = "income"
        record_applied(
            self.income_repo.conn,
            item_type=item_type,
            item_id=income.id,
            year_month=year_month,
            amount_pence=income.amount.pence,
        )
