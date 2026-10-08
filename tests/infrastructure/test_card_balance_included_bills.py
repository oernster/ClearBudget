"""Which ticked bills a typed card balance already contains, on real SQLite.

Paid says a bill happened, never when. A payment ticked before the balance
was typed is inside that figure; one the midnight fold ticks afterwards is
not. The save records the first kind; an upgraded budget is seeded once from
the hand ticks in each card's typed month.
"""

import sqlite3

import pytest

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.infrastructure.sqlite._migrations import (
    LATEST_VERSION,
    apply_pending,
    read_version,
)
from clear_budget.infrastructure.sqlite._schema import create_schema
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)

_VERSION_BEFORE_INCLUSIONS = 11
_TYPED = (2026, 10, 8)


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "budget.db")
    connection.row_factory = sqlite3.Row
    create_schema(connection)
    yield connection
    connection.close()


def _add_card(conn, name: str, *, typed_day: int | None) -> int:
    repo = SQLitePaymentMethodRepository(conn=conn)
    card = repo.add_credit_card(
        card=CreditCard(
            id=0,
            name=name,
            credit_limit=Amount(pence=475000),
            current_balance_used=Amount(pence=356385),
        )
    )
    year, month, _day = _TYPED
    repo.set_balance_applied(card_id=card.id, year=year, month=month, day=typed_day)
    return card.id


def _add_bill(conn, *, bill_id: int, method: int, target: int | None) -> None:
    category = "credit_payment" if target is not None else "subscriptions"
    conn.execute(
        "INSERT INTO bills (id, name, amount_pence, payment_method_id, category,"
        " bill_type, day_of_month, start_year, start_month, active, target_card_id)"
        " VALUES (?, 'bill', 100, ?, ?, 'fixed', 14, 2000, 1, 1, ?)",
        (bill_id, method, category, target),
    )


def _tick(conn, bill_id: int, *, by_fold: bool) -> None:
    year, month, _day = _TYPED
    conn.execute(
        "INSERT INTO bill_month_paid (bill_id, year, month) VALUES (?, ?, ?)",
        (bill_id, year, month),
    )
    if by_fold:
        conn.execute(
            "INSERT INTO balance_applied (item_type, item_id, year, month,"
            " amount_pence) VALUES ('bill', ?, ?, ?, -100)",
            (bill_id, year, month),
        )


def _included(conn, card_id: int) -> tuple[int, ...]:
    card = SQLitePaymentMethodRepository(conn=conn).get_credit_card_by_id(
        card_id=card_id
    )
    return card.balance_included_bill_ids


class TestTheRepository:
    def test_a_new_card_contains_nothing(self, conn):
        card_id = _add_card(conn, "Jaja", typed_day=_TYPED[2])
        assert _included(conn, card_id) == ()

    def test_the_recorded_bills_read_back_on_every_read(self, conn):
        card_id = _add_card(conn, "Jaja", typed_day=_TYPED[2])
        repo = SQLitePaymentMethodRepository(conn=conn)
        repo.set_balance_included_bills(card_id=card_id, bill_ids=(67, 54))
        assert _included(conn, card_id) == (54, 67)
        (listed,) = repo.get_all_credit_cards()
        assert listed.balance_included_bill_ids == (54, 67)

    def test_recording_again_replaces_the_set(self, conn):
        card_id = _add_card(conn, "Jaja", typed_day=_TYPED[2])
        repo = SQLitePaymentMethodRepository(conn=conn)
        repo.set_balance_included_bills(card_id=card_id, bill_ids=(67,))
        repo.set_balance_included_bills(card_id=card_id, bill_ids=())
        assert _included(conn, card_id) == ()

    def test_deleting_the_card_removes_its_set(self, conn):
        card_id = _add_card(conn, "Jaja", typed_day=_TYPED[2])
        repo = SQLitePaymentMethodRepository(conn=conn)
        repo.set_balance_included_bills(card_id=card_id, bill_ids=(67,))
        repo.hard_delete_credit_card(card_id=card_id)
        count = conn.execute(
            "SELECT COUNT(*) FROM card_balance_included_bills"
        ).fetchone()[0]
        assert count == 0

    def test_deleting_a_bill_removes_it_from_every_set(self, conn):
        # A reused id must not inherit "already inside the balance".
        card_id = _add_card(conn, "Jaja", typed_day=_TYPED[2])
        _add_bill(conn, bill_id=67, method=1, target=card_id)
        repo = SQLitePaymentMethodRepository(conn=conn)
        repo.set_balance_included_bills(card_id=card_id, bill_ids=(67,))
        SQLiteBillRepository(conn).hard_delete(bill_id=67)
        assert _included(conn, card_id) == ()


class TestTheUpgradeSeed:
    def _upgrade(self, conn) -> None:
        conn.execute("DROP TABLE card_balance_included_bills")
        conn.execute(
            "UPDATE schema_version SET version = ?", (_VERSION_BEFORE_INCLUSIONS,)
        )
        conn.commit()
        apply_pending(conn.cursor())

    def test_hand_ticked_card_bills_in_the_typed_month_are_seeded(self, conn):
        card_id = _add_card(conn, "Jaja", typed_day=_TYPED[2])
        _add_bill(conn, bill_id=67, method=1, target=card_id)  # payment
        _add_bill(conn, bill_id=54, method=card_id, target=None)  # charge
        _tick(conn, 67, by_fold=False)
        _tick(conn, 54, by_fold=False)
        self._upgrade(conn)
        assert _included(conn, card_id) == (54, 67)
        assert read_version(conn.cursor()) == LATEST_VERSION

    def test_a_tick_the_fold_made_is_not_seeded(self, conn):
        card_id = _add_card(conn, "Jaja", typed_day=_TYPED[2])
        _add_bill(conn, bill_id=13, method=1, target=card_id)
        _tick(conn, 13, by_fold=True)
        self._upgrade(conn)
        assert _included(conn, card_id) == ()

    def test_a_card_with_no_typed_day_is_not_seeded(self, conn):
        card_id = _add_card(conn, "Folded", typed_day=None)
        _add_bill(conn, bill_id=67, method=1, target=card_id)
        _tick(conn, 67, by_fold=False)
        self._upgrade(conn)
        assert _included(conn, card_id) == ()

    def test_another_cards_bill_is_not_seeded(self, conn):
        card_id = _add_card(conn, "Jaja", typed_day=_TYPED[2])
        _add_bill(conn, bill_id=67, method=1, target=card_id + 1)
        _tick(conn, 67, by_fold=False)
        self._upgrade(conn)
        assert _included(conn, card_id) == ()
