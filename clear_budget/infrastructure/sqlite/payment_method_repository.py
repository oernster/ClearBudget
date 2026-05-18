"""SQLite implementation of PaymentMethodRepository."""

import sqlite3
from dataclasses import dataclass

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.interfaces.payment_method_repository import (
    PaymentMethodRepository,
)
from clear_budget.domain.value_objects.amount import Amount


@dataclass
class SQLitePaymentMethodRepository:
    """SQLite-backed payment method repository."""

    conn: sqlite3.Connection

    def get_all_credit_cards(self, include_inactive: bool = False) -> list[CreditCard]:
        """Get all credit cards."""
        cursor = self.conn.cursor()
        where_clause = "" if include_inactive else "WHERE active = 1"
        query = f"""
            SELECT id, name, credit_limit_pence, current_balance_used_pence,
                   interest_rate_apr, payment_due_day, card_expiry_month, card_expiry_year,
                   minimum_payment_pence, active
            FROM credit_cards
            {where_clause}
            """
        print(f"[PAYMENT_METHOD_REPO] get_all_credit_cards(include_inactive={include_inactive})")
        print(f"[PAYMENT_METHOD_REPO] Query: {query}")
        cursor.execute(query)

        cards = []
        for row in cursor.fetchall():
            card = CreditCard(
                id=row["id"],
                name=row["name"],
                credit_limit=Amount(pence=row["credit_limit_pence"]),
                current_balance_used=Amount(pence=row["current_balance_used_pence"]),
                interest_rate_apr=row["interest_rate_apr"],
                payment_due_day=row["payment_due_day"],
                card_expiry_month=row["card_expiry_month"],
                card_expiry_year=row["card_expiry_year"],
                minimum_payment_pence=row["minimum_payment_pence"],
                active=row["active"],
            )
            cards.append(card)
            print(f"[PAYMENT_METHOD_REPO]   Found card: id={card.id}, name='{card.name}', active={card.active}")

        print(f"[PAYMENT_METHOD_REPO] Returned {len(cards)} cards")
        return cards

    def get_credit_card_by_id(self, *, card_id: int) -> CreditCard | None:
        """Get a credit card by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, credit_limit_pence, current_balance_used_pence,
                   interest_rate_apr, payment_due_day, card_expiry_month, card_expiry_year,
                   minimum_payment_pence, active
            FROM credit_cards WHERE id = ?
            """,
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
            active=row["active"],
        )

    def update_credit_card_balance(
        self, *, card_id: int, balance_used: int
    ) -> None:
        """Update a credit card's used balance (in pence)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE credit_cards SET current_balance_used_pence = ? WHERE id = ?",
            (balance_used, card_id),
        )
        self.conn.commit()

    def add_credit_card(self, *, card: CreditCard) -> CreditCard:
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
        print(f"[PAYMENT_METHOD_REPO] add_credit_card: Inserted/replaced '{card.name}' with id={card_id}")

        # Then add to credit_cards table with the payment method ID
        # Use INSERT OR REPLACE in case the card already exists
        cursor.execute(
            """
            INSERT OR REPLACE INTO credit_cards (
                id, name, credit_limit_pence, current_balance_used_pence,
                interest_rate_apr, payment_due_day, card_expiry_month, card_expiry_year,
                minimum_payment_pence, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
                card.active,
            ),
        )
        self.conn.commit()
        print(f"[PAYMENT_METHOD_REPO] add_credit_card: Inserted/replaced credit_cards record id={card_id}")

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
            active=card.active,
        )

    def update_credit_card(self, *, card: CreditCard) -> CreditCard:
        """Update an existing credit card."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE credit_cards SET
                name = ?,
                credit_limit_pence = ?,
                current_balance_used_pence = ?,
                interest_rate_apr = ?,
                payment_due_day = ?,
                card_expiry_month = ?,
                card_expiry_year = ?,
                minimum_payment_pence = ?,
                active = ?
            WHERE id = ?
            """,
            (
                card.name,
                card.credit_limit.pence,
                card.current_balance_used.pence,
                card.interest_rate_apr,
                card.payment_due_day,
                card.card_expiry_month,
                card.card_expiry_year,
                card.minimum_payment_pence,
                card.active,
                card.id,
            ),
        )
        self.conn.commit()
        return card

    def deactivate_credit_card(self, *, card_id: int) -> None:
        """Soft-delete a credit card by setting active=0."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE credit_cards SET active = 0 WHERE id = ?",
            (card_id,),
        )
        self.conn.commit()
