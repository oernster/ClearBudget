"""SQLite implementation of PaymentMethodRepository."""

import sqlite3
from dataclasses import dataclass

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.credit_limit_change import CreditLimitChange


@dataclass
class SQLitePaymentMethodRepository:
    """SQLite-backed payment method repository."""

    conn: sqlite3.Connection

    def get_all_credit_cards(  # pragma: no cover
        self, include_inactive: bool = False
    ) -> list[CreditCard]:
        """Get all credit cards."""
        cursor = self.conn.cursor()
        where_clause = "" if include_inactive else "WHERE active = 1"
        cursor.execute(f"""SELECT id, name,
                   credit_limit_pence, current_balance_used_pence,
                   interest_rate_apr, payment_due_day,
                   card_expiry_month, card_expiry_year,
                   minimum_payment_pence, minimum_payment_percent, active,
                   balance_applied_year, balance_applied_month, balance_applied_day
            FROM credit_cards {where_clause}""")
        return [
            CreditCard(
                id=row["id"],
                name=row["name"],
                credit_limit=Amount(pence=row["credit_limit_pence"]),
                current_balance_used=Amount(pence=row["current_balance_used_pence"]),
                interest_rate_apr=row["interest_rate_apr"],
                payment_due_day=row["payment_due_day"],
                card_expiry_month=row["card_expiry_month"],
                card_expiry_year=row["card_expiry_year"],
                minimum_payment_pence=row["minimum_payment_pence"],
                minimum_payment_percent=row["minimum_payment_percent"],
                active=row["active"],
                balance_applied_year=row["balance_applied_year"],
                balance_applied_month=row["balance_applied_month"],
                balance_applied_day=row["balance_applied_day"],
                scheduled_limit_changes=self._limit_changes_for(card_id=row["id"]),
            )
            for row in cursor.fetchall()
        ]

    def get_credit_card_by_id(  # pragma: no cover
        self, *, card_id: int
    ) -> CreditCard | None:
        """Get a credit card by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT id, name,
                   credit_limit_pence, current_balance_used_pence,
                   interest_rate_apr, payment_due_day,
                   card_expiry_month, card_expiry_year,
                   minimum_payment_pence, minimum_payment_percent, active,
                   balance_applied_year, balance_applied_month, balance_applied_day
            FROM credit_cards WHERE id = ?""",
            (card_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return CreditCard(
            id=row["id"],
            name=row["name"],
            credit_limit=Amount(pence=row["credit_limit_pence"]),
            current_balance_used=Amount(pence=row["current_balance_used_pence"]),
            interest_rate_apr=row["interest_rate_apr"],
            payment_due_day=row["payment_due_day"],
            card_expiry_month=row["card_expiry_month"],
            card_expiry_year=row["card_expiry_year"],
            minimum_payment_pence=row["minimum_payment_pence"],
            minimum_payment_percent=row["minimum_payment_percent"],
            active=row["active"],
            balance_applied_year=row["balance_applied_year"],
            balance_applied_month=row["balance_applied_month"],
            balance_applied_day=row["balance_applied_day"],
            scheduled_limit_changes=self._limit_changes_for(card_id=row["id"]),
        )

    def update_credit_card_balance(  # pragma: no cover
        self, *, card_id: int, balance_used: int
    ) -> None:
        """Update a credit card's used balance (in pence)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE credit_cards SET current_balance_used_pence = ? WHERE id = ?",
            (balance_used, card_id),
        )
        self.conn.commit()

    def set_balance_applied(  # pragma: no cover
        self, *, card_id: int, year: int, month: int, day: int | None = None
    ) -> None:
        """Stamp the period whose state is folded into current_balance_used.

        A `day` marks a mid-month manual entry (balance as-of that day); None
        marks a whole-month fold with no day anchor.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE credit_cards"
            " SET balance_applied_year = ?, balance_applied_month = ?,"
            " balance_applied_day = ?"
            " WHERE id = ?",
            (year, month, day, card_id),
        )
        self.conn.commit()

    def _limit_changes_for(  # pragma: no cover
        self, *, card_id: int
    ) -> tuple[CreditLimitChange, ...]:
        """Load a card's scheduled limit changes, ordered by effective date."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT effective_year, effective_month, effective_day, new_limit_pence"
            " FROM credit_limit_changes WHERE card_id = ?"
            " ORDER BY effective_year, effective_month, effective_day, id",
            (card_id,),
        )
        return tuple(
            CreditLimitChange(
                effective_year=row["effective_year"],
                effective_month=row["effective_month"],
                effective_day=row["effective_day"],
                new_limit=Amount(pence=row["new_limit_pence"]),
            )
            for row in cursor.fetchall()
        )

    def set_credit_limit_changes(  # pragma: no cover
        self, *, card_id: int, changes: tuple[CreditLimitChange, ...]
    ) -> None:
        """Replace all scheduled limit changes for a card (delete then insert)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM credit_limit_changes WHERE card_id = ?", (card_id,))
        for change in changes:
            cursor.execute(
                "INSERT INTO credit_limit_changes (card_id, effective_year,"
                " effective_month, effective_day, new_limit_pence)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    card_id,
                    change.effective_year,
                    change.effective_month,
                    change.effective_day,
                    change.new_limit.pence,
                ),
            )
        self.conn.commit()

    def update_credit_card_limit(  # pragma: no cover
        self, *, card_id: int, limit_pence: int
    ) -> None:
        """Update a credit card's current credit limit (in pence)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE credit_cards SET credit_limit_pence = ? WHERE id = ?",
            (limit_pence, card_id),
        )
        self.conn.commit()

    def add_credit_card(self, *, card: CreditCard) -> CreditCard:  # pragma: no cover
        """Create a new credit card."""
        cursor = self.conn.cursor()

        # Add to payment_methods table FIRST (parent record)
        # Use INSERT OR REPLACE in case the card already exists
        cursor.execute(
            """
            INSERT OR REPLACE INTO payment_methods (name, type)
            VALUES (?, ?)
            """,
            (card.name, "credit_card"),
        )
        # For INSERT OR REPLACE, we need to query to get the ID
        cursor.execute("SELECT id FROM payment_methods WHERE name = ?", (card.name,))
        card_id = cursor.fetchone()[0]

        # Then add to credit_cards table with the payment method ID
        # Use INSERT OR REPLACE in case the card already exists
        cursor.execute(
            """INSERT OR REPLACE INTO credit_cards (
                id, name, credit_limit_pence, current_balance_used_pence,
                interest_rate_apr, payment_due_day, card_expiry_month, card_expiry_year,
                minimum_payment_pence, minimum_payment_percent, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                card_id,
                card.name,
                card.credit_limit.pence,
                card.current_balance_used.pence,
                card.interest_rate_apr,
                card.payment_due_day,
                card.card_expiry_month,
                card.card_expiry_year,
                card.minimum_payment_pence,
                card.minimum_payment_percent,
                card.active,
            ),
        )
        self.conn.commit()
        return CreditCard(
            id=card_id,
            name=card.name,
            credit_limit=card.credit_limit,
            current_balance_used=card.current_balance_used,
            interest_rate_apr=card.interest_rate_apr,
            payment_due_day=card.payment_due_day,
            card_expiry_month=card.card_expiry_month,
            card_expiry_year=card.card_expiry_year,
            minimum_payment_pence=card.minimum_payment_pence,
            minimum_payment_percent=card.minimum_payment_percent,
            active=card.active,
        )

    def update_credit_card(self, *, card: CreditCard) -> CreditCard:  # pragma: no cover
        """Update an existing credit card."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE credit_cards SET name=?, credit_limit_pence=?,
                current_balance_used_pence=?, interest_rate_apr=?, payment_due_day=?,
                card_expiry_month=?, card_expiry_year=?, minimum_payment_pence=?,
                minimum_payment_percent=?, active=?
            WHERE id=?""",
            (
                card.name,
                card.credit_limit.pence,
                card.current_balance_used.pence,
                card.interest_rate_apr,
                card.payment_due_day,
                card.card_expiry_month,
                card.card_expiry_year,
                card.minimum_payment_pence,
                card.minimum_payment_percent,
                card.active,
                card.id,
            ),
        )
        self.conn.commit()
        return card

    def deactivate_credit_card(self, *, card_id: int) -> None:  # pragma: no cover
        """Soft-delete a credit card by setting active=0."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE credit_cards SET active = 0 WHERE id = ?", (card_id,))
        self.conn.commit()

    def set_card_active(  # pragma: no cover
        self, *, card_id: int, active: bool
    ) -> None:
        """Set active state of a credit card."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE credit_cards SET active = ? WHERE id = ?",
            (1 if active else 0, card_id),
        )
        self.conn.commit()

    def hard_delete_credit_card(self, *, card_id: int) -> None:  # pragma: no cover
        """Permanently remove a credit card from both tables."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM credit_cards WHERE id = ?", (card_id,))
        cursor.execute("DELETE FROM payment_methods WHERE id = ?", (card_id,))
        self.conn.commit()
