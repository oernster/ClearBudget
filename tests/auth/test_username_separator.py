"""A username may not contain the separator budget file names use.

A named budget is `budget_<safe user>__<slug>.db`. The safe form of a name
with two spaces or punctuation marks in a row holds that same `__`, so the
first budget of `alice  bob` is `budget_alice__bob.db`: alice's budget "Bob".
Measured: such an account was created and opened alice's figures, because an
unstamped file cannot say whose it is. Account creation refuses the name.
"""

from __future__ import annotations

import pytest

from clear_budget.auth.user_store import UsernameCollisionError, UserStore
from clear_budget.shared import budget_registry as reg
from clear_budget.shared.config import Config
from tests.auth.backup_helpers import marker_of, real_budget_db


@pytest.fixture()
def store():
    s = UserStore(Config.users_db_path())
    yield s
    s.close()


def test_a_name_holding_the_separator_cannot_take_anothers_budget(store):
    store.create_user("alice", "password-1")
    record = reg.create_budget("alice", "Bob")
    alice_bob = Config.for_user_budget("alice", record.slug).db_path
    real_budget_db(alice_bob, marker="ALICE-BOB-PRIVATE")  # unstamped

    with pytest.raises(UsernameCollisionError, match="in a row"):
        store.create_user("alice  bob", "password-2")

    assert store.find_user("alice  bob") is None
    assert marker_of(alice_bob) == "ALICE-BOB-PRIVATE"


@pytest.mark.parametrize("name", ["a  b", "a__b", "a_ b", "a.,b", "x  "])
def test_every_spelling_that_yields_the_separator_is_refused(store, name):
    with pytest.raises(UsernameCollisionError):
        store.create_user(name, "password-1")
    assert not store.has_users()


@pytest.mark.parametrize("name", ["a b", "a_b", "a-b", "a.b", "o'brien"])
def test_single_marks_between_words_are_allowed(store, name):
    store.create_user(name, "password-1")
    assert store.find_user(name) is not None
