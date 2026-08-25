"""SQLite implementation of CommitmentRepository.

A date is three integers here, matching `credit_limit_changes`: the schema
has always stored a calendar day that way and one convention is easier to
read than two. The row is turned back into a `Commitment` in exactly one
place, so a column added later has a single place to be handled.
"""

import sqlite3
from dataclasses import dataclass, replace
from datetime import date

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.recurrence import Recurrence
from clear_budget.domain.value_objects.year_month import YearMonth

_COLUMNS = (
    "id, name, amount_pence, due_year, due_month, due_day, recurrence,"
    " already_held_pence, category, active, created_year, created_month,"
    " final_year, final_month"
)


def _to_commitment(row) -> Commitment:
    """One row as a domain commitment."""
    final_year = row["final_year"]
    final_month = row["final_month"]
    return Commitment(
        id=row["id"],
        name=row["name"],
        amount=Amount(pence=row["amount_pence"]),
        due_date=date(row["due_year"], row["due_month"], row["due_day"]),
        recurrence=Recurrence.parse(row["recurrence"]),
        created_month=YearMonth(year=row["created_year"], month=row["created_month"]),
        already_held=Amount(pence=row["already_held_pence"]),
        category=row["category"],
        active=bool(row["active"]),
        final_month=(
            YearMonth(year=final_year, month=final_month)
            if final_year is not None and final_month is not None
            else None
        ),
    )


@dataclass
class SQLiteCommitmentRepository:
    """SQLite-backed commitment repository."""

    conn: sqlite3.Connection

    def list_all(self, *, include_inactive: bool = False) -> list[Commitment]:
        """Every commitment, ordered by the day it falls due."""
        cursor = self.conn.cursor()
        active_filter = "" if include_inactive else " WHERE active = 1"
        cursor.execute(
            f"SELECT {_COLUMNS} FROM commitments{active_filter}"
            " ORDER BY due_year, due_month, due_day, id"
        )
        return [_to_commitment(row) for row in cursor.fetchall()]

    def list_for_month(self, *, year_month: YearMonth) -> list[Commitment]:
        """Those being reserved for during `year_month`.

        The window is decided by the entity rather than by SQL, so the answer
        here and the answer the floor gives can never drift apart.
        """
        return [c for c in self.list_all() if c.applies_to(year_month)]

    def get_by_id(self, *, commitment_id: int) -> Commitment | None:
        """One commitment by id; None when there is none."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT {_COLUMNS} FROM commitments WHERE id = ?", (commitment_id,)
        )
        row = cursor.fetchone()
        return _to_commitment(row) if row else None

    def add(self, *, commitment: Commitment) -> Commitment:
        """Store a new commitment and return it carrying its assigned id."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO commitments ("
            " name, amount_pence, due_year, due_month, due_day, recurrence,"
            " already_held_pence, category, active, created_year,"
            " created_month, final_year, final_month"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._values(commitment),
        )
        self.conn.commit()
        return replace(commitment, id=cursor.lastrowid)

    def update(self, *, commitment: Commitment) -> Commitment:
        """Store changes to an existing commitment."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE commitments SET"
            " name = ?, amount_pence = ?, due_year = ?, due_month = ?,"
            " due_day = ?, recurrence = ?, already_held_pence = ?,"
            " category = ?, active = ?, created_year = ?, created_month = ?,"
            " final_year = ?, final_month = ? WHERE id = ?",
            (*self._values(commitment), commitment.id),
        )
        self.conn.commit()
        return commitment

    def end_from(self, *, commitment_id: int, final_month: YearMonth) -> None:
        """Stop reserving after `final_month`, keeping the months it ran in.

        The ending rule bills and income already follow: a commitment that
        stops carries a final month rather than leaving, so a month that
        really did hold a reserve still reports it when it is read back.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE commitments SET final_year = ?, final_month = ? WHERE id = ?",
            (final_month.year, final_month.month, commitment_id),
        )
        self.conn.commit()

    def delete(self, *, commitment_id: int) -> None:
        """Remove a commitment outright, including the months it ran in."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM commitments WHERE id = ?", (commitment_id,))
        self.conn.commit()

    @staticmethod
    def _values(commitment: Commitment) -> tuple:
        """The column values for one commitment, in schema order."""
        final = commitment.final_month
        return (
            commitment.name,
            commitment.amount.pence,
            commitment.due_date.year,
            commitment.due_date.month,
            commitment.due_date.day,
            str(commitment.recurrence),
            commitment.already_held.pence,
            commitment.category,
            int(commitment.active),
            commitment.created_month.year,
            commitment.created_month.month,
            final.year if final else None,
            final.month if final else None,
        )
