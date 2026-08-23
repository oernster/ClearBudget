"""Tests for the named-budget registry.

The rules these hold to are the ones a user would notice:

  * an install that predates named budgets sees exactly one budget, on the
    file it always used, with nothing moved;
  * a damaged or hand-edited index degrades to that same single budget rather
    than to an error, because the databases are the data and the index is only
    the map to them;
  * creating a budget never touches another one; the last one can never be
    deleted.

Every test runs against the autouse scratch data directory (see conftest), so
none of them can see or write the real ~/.clearbudget.
"""

import json

import pytest

from clear_budget.shared import budget_registry as reg
from clear_budget.shared.config import LEGACY_BUDGET_SLUG, Config

_USER = "alice"


def _index_path():
    return Config.budgets_index_path(_USER)


def _write_index(payload) -> None:
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        payload if isinstance(payload, str) else json.dumps(payload),
        encoding="utf-8",
    )


# --- the install that predates named budgets ------------------------------


def test_a_user_with_no_index_has_one_budget_on_the_legacy_file():
    index = reg.load_index(_USER)
    assert index.budgets == (
        reg.BudgetRecord(LEGACY_BUDGET_SLUG, reg.DEFAULT_BUDGET_NAME),
    )
    assert index.active == LEGACY_BUDGET_SLUG
    assert reg.active_db_path(_USER) == Config.for_user(_USER).db_path


def test_the_legacy_budget_keeps_the_unsuffixed_filename():
    """Naming budgets must move no data, so the first file is untouched."""
    assert (
        Config.for_user_budget(_USER, LEGACY_BUDGET_SLUG).db_path
        == Config.for_user(_USER).db_path
    )
    assert Config.for_user(_USER).db_path.name == "budget_alice.db"


def test_a_named_budget_gets_its_slug_after_a_double_underscore():
    assert Config.for_user_budget(_USER, "holiday").db_path.name == (
        "budget_alice__holiday.db"
    )


def test_reading_the_index_does_not_create_it():
    reg.load_index(_USER)
    assert not _index_path().exists()


# --- a damaged index degrades, never crashes ------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not json at all",
        "[]",
        '"budgets"',
        "7",
        {"budgets": "nope"},
        {"budgets": []},
        {"budgets": [1, "two", None]},
        {"budgets": [{"slug": 1, "name": "ok"}]},
        {"budgets": [{"slug": "s", "name": 2}]},
        {"budgets": [{"slug": "s", "name": "   "}]},
        {"budgets": [{"slug": "s"}]},
        {"nothing": "useful"},
    ],
)
def test_an_unusable_index_means_the_single_legacy_budget(payload):
    _write_index(payload)
    assert reg.load_index(_USER) == reg._default_index()


def test_unusable_records_are_dropped_and_the_good_ones_kept():
    _write_index(
        {
            "active": "b",
            "budgets": [{"slug": "b", "name": " Business "}, {"bad": True}],
        }
    )
    index = reg.load_index(_USER)
    assert index.budgets == (reg.BudgetRecord("b", "Business"),)


def test_a_non_string_active_falls_back_to_the_first_budget():
    _write_index({"active": 9, "budgets": [{"slug": "b", "name": "Business"}]})
    assert reg.load_index(_USER).active == "b"


def test_an_active_slug_that_no_longer_exists_still_opens_something():
    """A half-written or hand-edited index must not leave the user with none."""
    _write_index({"active": "ghost", "budgets": [{"slug": "b", "name": "Business"}]})
    assert reg.load_index(_USER).active_record().slug == "b"


def test_an_unwritable_index_is_swallowed(monkeypatch):
    """The databases are untouched, so the only cost is not remembering."""

    def _boom(*_args, **_kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(type(_index_path()), "write_text", _boom)
    reg.store_index(_USER, reg._default_index())
    assert not _index_path().exists()


# --- slugs -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Holiday", "holiday"),
        ("Holiday Fund", "holiday_fund"),
        ("  Trip: 2027!  ", "trip_2027"),
        ("a---b", "a_b"),
        ("£££", "budget"),
        ("", "budget"),
    ],
)
def test_slugs_are_filesystem_safe(name, expected):
    assert reg.safe_slug(name) == expected


def test_a_slug_never_contains_a_double_underscore():
    """It is the separator in the filename, so a slug holding one would alias."""
    assert "__" not in reg.safe_slug("a  ,  b")


def test_colliding_slugs_are_numbered_apart():
    reg.create_budget(_USER, "Holiday Fund")
    reg.create_budget(_USER, "holiday:fund")
    reg.create_budget(_USER, "HOLIDAY FUND!")
    slugs = [record.slug for record in reg.load_index(_USER).budgets]
    assert slugs == ["", "holiday_fund", "holiday_fund_2", "holiday_fund_3"]


# --- creating --------------------------------------------------------------


def test_creating_a_budget_leaves_the_existing_one_alone_and_switches():
    created = reg.create_budget(_USER, "Business")
    index = reg.load_index(_USER)
    assert index.active == created.slug
    assert [record.name for record in index.budgets] == [
        reg.DEFAULT_BUDGET_NAME,
        "Business",
    ]


def test_creating_writes_the_index_but_not_the_database():
    record = reg.create_budget(_USER, "Business")
    assert _index_path().exists()
    assert not Config.for_user_budget(_USER, record.slug).db_path.exists()


@pytest.mark.parametrize("name", ["", "   "])
def test_a_budget_needs_a_name(name):
    with pytest.raises(reg.BudgetRegistryError, match="needs a name"):
        reg.create_budget(_USER, name)


def test_two_budgets_cannot_share_a_name_whatever_the_case():
    reg.create_budget(_USER, "Business")
    with pytest.raises(reg.BudgetRegistryError, match="already have a budget"):
        reg.create_budget(_USER, "  business  ")


def test_names_are_trimmed():
    assert reg.create_budget(_USER, "  Business  ").name == "Business"


# --- switching -------------------------------------------------------------


def test_switching_changes_which_database_a_session_opens():
    record = reg.create_budget(_USER, "Business")
    reg.set_active(_USER, LEGACY_BUDGET_SLUG)
    assert reg.active_db_path(_USER) == Config.for_user(_USER).db_path
    reg.set_active(_USER, record.slug)
    assert (
        reg.active_db_path(_USER) == Config.for_user_budget(_USER, record.slug).db_path
    )


def test_switching_to_a_budget_that_is_gone_is_refused():
    with pytest.raises(reg.BudgetRegistryError, match="no longer exists"):
        reg.set_active(_USER, "ghost")


# --- renaming --------------------------------------------------------------


def test_renaming_keeps_the_slug_so_the_file_never_moves():
    record = reg.create_budget(_USER, "Business")
    reg.rename_budget(_USER, record.slug, "Company")
    renamed = reg.load_index(_USER).find(record.slug)
    assert renamed.name == "Company"
    assert renamed.slug == record.slug


def test_renaming_a_budget_to_its_own_name_is_allowed():
    """Only OTHER budgets count as a clash; else a no-op rename would fail."""
    record = reg.create_budget(_USER, "Business")
    reg.rename_budget(_USER, record.slug, "Business")
    assert reg.load_index(_USER).find(record.slug).name == "Business"


def test_renaming_onto_another_budgets_name_is_refused():
    record = reg.create_budget(_USER, "Business")
    with pytest.raises(reg.BudgetRegistryError, match="already have a budget"):
        reg.rename_budget(_USER, record.slug, reg.DEFAULT_BUDGET_NAME)


def test_renaming_needs_a_name():
    record = reg.create_budget(_USER, "Business")
    with pytest.raises(reg.BudgetRegistryError, match="needs a name"):
        reg.rename_budget(_USER, record.slug, "  ")


def test_renaming_a_budget_that_is_gone_is_refused():
    with pytest.raises(reg.BudgetRegistryError, match="no longer exists"):
        reg.rename_budget(_USER, "ghost", "Company")


# --- deleting --------------------------------------------------------------


def _touch_db(slug: str):
    path = Config.for_user_budget(_USER, slug).db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("db", encoding="utf-8")
    return path


def test_deleting_takes_the_database_and_its_sqlite_sidecars():
    record = reg.create_budget(_USER, "Business")
    db = _touch_db(record.slug)
    wal = db.with_name(db.name + "-wal")
    wal.write_text("wal", encoding="utf-8")
    reg.set_active(_USER, LEGACY_BUDGET_SLUG)

    reg.delete_budget(_USER, record.slug)

    assert not db.exists()
    assert not wal.exists()
    assert reg.load_index(_USER).find(record.slug) is None


def test_deleting_an_inactive_budget_leaves_the_active_one_alone():
    record = reg.create_budget(_USER, "Business")
    spare = reg.create_budget(_USER, "Holiday")
    reg.set_active(_USER, record.slug)
    assert reg.delete_budget(_USER, spare.slug) == record.slug


def test_deleting_the_active_budget_moves_active_to_a_survivor():
    record = reg.create_budget(_USER, "Business")
    assert reg.load_index(_USER).active == record.slug
    assert reg.delete_budget(_USER, record.slug) == LEGACY_BUDGET_SLUG


def test_the_only_budget_can_never_be_deleted():
    with pytest.raises(reg.BudgetRegistryError, match="only budget"):
        reg.delete_budget(_USER, LEGACY_BUDGET_SLUG)
    assert reg.load_index(_USER).budgets


def test_deleting_a_budget_that_is_gone_is_refused():
    with pytest.raises(reg.BudgetRegistryError, match="no longer exists"):
        reg.delete_budget(_USER, "ghost")


def test_deleting_a_database_that_was_never_created_is_not_an_error():
    record = reg.create_budget(_USER, "Business")
    reg.set_active(_USER, LEGACY_BUDGET_SLUG)
    reg.delete_budget(_USER, record.slug)
    assert reg.load_index(_USER).find(record.slug) is None


# --- deleting the whole account -------------------------------------------


def test_deleting_an_account_takes_every_budget_it_owns():
    """Deleting only the legacy file would orphan the named ones on disk."""
    business = reg.create_budget(_USER, "Business")
    holiday = reg.create_budget(_USER, "Holiday")
    legacy_db = _touch_db(LEGACY_BUDGET_SLUG)
    business_db = _touch_db(business.slug)
    holiday_db = _touch_db(holiday.slug)

    reg.delete_all_budgets(_USER)

    assert not legacy_db.exists()
    assert not business_db.exists()
    assert not holiday_db.exists()
    assert not _index_path().exists()


def test_deleting_an_account_that_never_named_a_budget_takes_its_database():
    legacy_db = _touch_db(LEGACY_BUDGET_SLUG)
    reg.delete_all_budgets(_USER)
    assert not legacy_db.exists()
