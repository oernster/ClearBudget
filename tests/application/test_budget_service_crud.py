"""BudgetService pass-throughs that nothing else exercised.

Ported from two scripts that sat at the repository root, `test_add_bill.py` and
`test_functionality.py`. They were named like tests but were never collected
(`pyproject.toml` sets `testpaths = ["tests"]`), ran against the user's REAL
database in `~/.clearbudget` and asserted almost nothing.

Nearly everything they touched is covered under `tests/` already. Two things
were not: editing a bill and listing credit cards. Both are here, against a
temp SQLite database like the rest of the application tests, so what the
scripts were reaching for is kept and the risk they carried is not.

`get_credit_cards` matters more than a pass-through usually would: the whole of
`SQLitePaymentMethodRepository` is marked `# pragma: no cover`, so the coverage
gate says nothing about it. These read through the real repository rather than
a fake, which is the only way the assertions mean anything here.
"""

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)

_MONTH = YearMonth(2026, 5)
_BANK_ACCOUNT_ID = 1


@pytest.fixture()
def cards_repo(tmp_path):
    """The card repository the service is wired to, for direct seeding."""
    db = Database(tmp_path / "test.db")
    db.connect()
    db.create_schema()
    yield SQLitePaymentMethodRepository(db.conn), db
    db.close()


@pytest.fixture()
def budget_service(cards_repo):
    """BudgetService wired to a temp SQLite database."""
    payment_method_repo, db = cards_repo
    return BudgetService(
        bill_repo=SQLiteBillRepository(db.conn),
        income_repo=SQLiteIncomeSourceRepository(db.conn),
        payment_method_repo=payment_method_repo,
        month_generator=MonthGenerator(
            SQLiteBillRepository(db.conn), SQLiteIncomeSourceRepository(db.conn)
        ),
    )


def _bill(**overrides) -> Bill:
    fields = {
        "id": 0,
        "name": "Broadband",
        "amount": Amount.from_pounds(50.00),
        "payment_method_id": _BANK_ACCOUNT_ID,
        "category": "utilities",
        "bill_type": "fixed",
        "day_of_month": 10,
        "start_ym": _MONTH,
        "end_ym": None,
        "active": True,
    }
    fields.update(overrides)
    return Bill(**fields)


def _card(name: str, *, active: int = 1) -> CreditCard:
    return CreditCard(
        id=0,
        name=name,
        credit_limit=Amount.from_pounds(2000.00),
        current_balance_used=Amount.from_pounds(250.00),
        payment_due_day=15,
        active=active,
    )


class TestUpdatingABill:
    """`update_bill` had no test at all, on any layer above the repository."""

    def test_every_edited_field_is_persisted(self, budget_service) -> None:
        added = budget_service.add_bill(bill=_bill())

        budget_service.update_bill(
            bill=_bill(
                id=added.id,
                name="Broadband and phone",
                amount=Amount.from_pounds(64.50),
                category="discretionary",
                bill_type="variable",
                day_of_month=22,
            )
        )

        stored = budget_service.bill_repo.get_by_id(bill_id=added.id)
        assert stored.name == "Broadband and phone"
        assert stored.amount == Amount.from_pounds(64.50)
        assert stored.category == "discretionary"
        assert stored.bill_type == "variable"
        assert stored.day_of_month == 22

    def test_the_edit_keeps_the_same_bill_rather_than_adding_one(
        self, budget_service
    ) -> None:
        added = budget_service.add_bill(bill=_bill())

        returned = budget_service.update_bill(
            bill=_bill(id=added.id, amount=Amount.from_pounds(75.00))
        )

        assert returned.id == added.id
        summary = budget_service.get_month_summary(year_month=_MONTH)
        assert [b.id for b in summary.bills] == [added.id]

    def test_the_edited_amount_reaches_the_month_summary(self, budget_service) -> None:
        """The figure the user sees, not just the row in the table."""
        added = budget_service.add_bill(bill=_bill(amount=Amount.from_pounds(50.00)))

        budget_service.update_bill(
            bill=_bill(id=added.id, amount=Amount.from_pounds(75.00))
        )

        summary = budget_service.get_month_summary(year_month=_MONTH)
        assert summary.total_bills == Amount.from_pounds(75.00)


class TestListingCreditCards:
    """`get_credit_cards` had no test; its repository is un-gated."""

    def test_no_cards_reads_as_an_empty_list(self, budget_service) -> None:
        assert budget_service.get_credit_cards() == []

    def test_active_cards_are_listed(self, budget_service, cards_repo) -> None:
        repo, _db = cards_repo
        repo.add_credit_card(card=_card("Everyday"))

        cards = budget_service.get_credit_cards()

        assert [c.name for c in cards] == ["Everyday"]
        assert cards[0].credit_limit == Amount.from_pounds(2000.00)
        assert cards[0].current_balance_used == Amount.from_pounds(250.00)

    def test_a_closed_card_is_left_out_by_default(
        self, budget_service, cards_repo
    ) -> None:
        repo, _db = cards_repo
        repo.add_credit_card(card=_card("Everyday"))
        closed = repo.add_credit_card(card=_card("Old store card"))
        repo.set_card_active(card_id=closed.id, active=False)

        assert [c.name for c in budget_service.get_credit_cards()] == ["Everyday"]

    def test_a_closed_card_is_included_when_asked_for(
        self, budget_service, cards_repo
    ) -> None:
        repo, _db = cards_repo
        repo.add_credit_card(card=_card("Everyday"))
        closed = repo.add_credit_card(card=_card("Old store card"))
        repo.set_card_active(card_id=closed.id, active=False)

        names = [c.name for c in budget_service.get_credit_cards(include_inactive=True)]

        assert sorted(names) == ["Everyday", "Old store card"]
