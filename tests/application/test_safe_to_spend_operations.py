"""Tests for the safe-to-spend adapter and settings on BudgetService."""

from datetime import date

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.services.safe_to_spend import (
    HorizonStrategy,
    SafeToSpendResult,
)
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

_TODAY = date(2026, 7, 26)
_JULY = YearMonth(2026, 7)
_AUGUST = YearMonth(2026, 8)


@pytest.fixture()
def budget_service(tmp_path):
    """BudgetService wired to a temp SQLite database."""
    db = Database(tmp_path / "test.db")
    db.connect()
    db.create_schema()
    svc = BudgetService(
        bill_repo=SQLiteBillRepository(db.conn),
        income_repo=SQLiteIncomeSourceRepository(db.conn),
        payment_method_repo=SQLitePaymentMethodRepository(db.conn),
        month_generator=MonthGenerator(
            SQLiteBillRepository(db.conn), SQLiteIncomeSourceRepository(db.conn)
        ),
    )
    yield svc
    db.close()


def _seed_balance(conn, *, pence: int, iso: str) -> None:
    day = date.fromisoformat(iso).day
    for key, value in (
        ("bank_balance", str(pence)),
        ("bank_balance_day", str(day)),
        ("bank_balance_date", iso),
    ):
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()


def _bill(
    name: str, pence: int, day, *, start: YearMonth | None = None, method: int = 1
) -> Bill:
    return Bill(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        payment_method_id=method,
        category="utilities",
        bill_type="fixed",
        day_of_month=day,
        start_ym=start or YearMonth(2026, 1),
        end_ym=None,
        target_card_id=None,
    )


def _income(name: str, pence: int, day) -> IncomeSource:
    return IncomeSource(
        id=0, name=name, amount=Amount(pence=pence), is_reliable=True, day_of_month=day
    )


class TestSettings:
    def test_floor_defaults_to_zero_and_round_trips(self, budget_service):
        assert budget_service.get_safe_to_spend_floor() == Amount(pence=0)
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=10000))
        assert budget_service.get_safe_to_spend_floor() == Amount(pence=10000)

    def test_horizon_defaults_to_full_forecast_and_round_trips(self, budget_service):
        assert (
            budget_service.get_safe_to_spend_horizon() is HorizonStrategy.FULL_FORECAST
        )
        budget_service.set_safe_to_spend_horizon(
            horizon=HorizonStrategy.UNTIL_NEXT_INCOME
        )
        assert (
            budget_service.get_safe_to_spend_horizon()
            is HorizonStrategy.UNTIL_NEXT_INCOME
        )


class TestSafeToSpend:
    def test_bound_by_a_bill_before_the_next_income(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 200000, 1))
        budget_service.add_bill(bill=_bill("Water", 30000, 28))
        budget_service.set_safe_to_spend_horizon(
            horizon=HorizonStrategy.UNTIL_NEXT_INCOME
        )
        result = budget_service.get_safe_to_spend(today=_TODAY)
        # Horizon runs to 31 July, the day before the August salary; the
        # water bill on the 28th sets the minimum.
        assert result.horizon_end == date(2026, 7, 31)
        assert result.binding_day == date(2026, 7, 28)
        assert result.amount_pence == 70000

    def test_a_bill_after_the_next_income_is_seen_only_by_full_forecast(
        self, budget_service
    ):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 50000, 1))
        budget_service.add_bill(bill=_bill("Rent", 140000, 10, start=_AUGUST))
        budget_service.set_safe_to_spend_horizon(
            horizon=HorizonStrategy.UNTIL_NEXT_INCOME
        )
        until_income = budget_service.get_safe_to_spend(today=_TODAY)
        assert until_income.amount_pence == 100000
        assert until_income.horizon_end == date(2026, 7, 31)

        budget_service.set_safe_to_spend_horizon(horizon=HorizonStrategy.FULL_FORECAST)
        full = budget_service.get_safe_to_spend(today=_TODAY)
        assert full.amount_pence < until_income.amount_pence
        assert full.binding_day >= date(2026, 8, 10)
        assert full.first_breach_day is not None

    def test_floor_reduces_the_amount_by_exactly_the_floor(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=80000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 200000, 1))
        budget_service.add_bill(bill=_bill("Water", 20000, 28))
        without = budget_service.get_safe_to_spend(today=_TODAY)
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=15000))
        with_floor = budget_service.get_safe_to_spend(today=_TODAY)
        assert without.amount_pence - with_floor.amount_pence == 15000

    def test_income_received_early_does_not_end_the_horizon(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=60000, iso="2026-07-26")
        bonus = budget_service.add_income(income=_income("Bonus", 20000, 28))
        budget_service.mark_income_received_for_month(
            income_id=bonus.id, year_month=_JULY
        )
        budget_service.set_safe_to_spend_horizon(
            horizon=HorizonStrategy.UNTIL_NEXT_INCOME
        )
        result = budget_service.get_safe_to_spend(today=_TODAY)
        # The 28 July bonus is already inside the stored balance, so the next
        # income event is the August one; the horizon runs to the day before.
        assert result.horizon_end == date(2026, 8, 27)

    def test_a_pending_income_later_this_month_ends_the_horizon(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=60000, iso="2026-07-26")
        budget_service.add_income(income=_income("Bonus", 20000, 28))
        budget_service.set_safe_to_spend_horizon(
            horizon=HorizonStrategy.UNTIL_NEXT_INCOME
        )
        result = budget_service.get_safe_to_spend(today=_TODAY)
        assert result.horizon_end == date(2026, 7, 27)

    def test_undated_income_counts_on_day_one(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=50000, iso="2026-07-26")
        budget_service.add_income(income=_income("Odd jobs", 10000, None))
        budget_service.set_safe_to_spend_horizon(
            horizon=HorizonStrategy.UNTIL_NEXT_INCOME
        )
        result = budget_service.get_safe_to_spend(today=_TODAY)
        # The next undated income lands 1 August, so the horizon is July's end.
        assert result.horizon_end == date(2026, 7, 31)

    def test_shortfall_is_signed_not_clamped(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=10000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 200000, 1))
        budget_service.add_bill(bill=_bill("Rent", 45000, 28))
        result = budget_service.get_safe_to_spend(today=_TODAY)
        assert result.amount_pence == -35000
        assert result.binding_day == date(2026, 7, 28)

    def test_multi_month_chain_binds_in_a_later_month(self, budget_service):
        # A standing deficit: the balance erodes month on month, so under
        # FULL_FORECAST the binding day sits deep in the window.
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 50000, 1))
        budget_service.add_bill(bill=_bill("Rent", 80000, 10))
        budget_service.set_safe_to_spend_horizon(horizon=HorizonStrategy.FULL_FORECAST)
        result = budget_service.get_safe_to_spend(today=_TODAY)
        assert result.amount_pence < 0
        assert result.binding_day.year > 2026 or result.binding_day.month > 8

    def test_default_today_argument(self, budget_service):
        result = budget_service.get_safe_to_spend()
        assert isinstance(result, SafeToSpendResult)
        assert result.amount_pence == 0

    def test_current_month_runs_on_the_still_due_convention(self, budget_service):
        """The chain's current-month close equals the Solvency panel's figure.

        An undated bill counts at its prorated REMAINING portion, because the
        elapsed portion is already inside the stored balance. Charging the
        full amount again (the raw month-graph convention) understated every
        later month's opening and called days unsafe that the panel's own
        timeline showed as safe. A card bill never touches the chain.
        """
        from datetime import timedelta

        from clear_budget.domain.entities.credit_card import CreditCard
        from clear_budget.domain.services._prorating import (
            days_in_month,
            prorate_remaining_pence,
        )

        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_bill(bill=_bill("Food", 31000, None))
        budget_service.add_bill(bill=_bill("Water", 5000, 28))
        card = budget_service.payment_method_repo.add_credit_card(
            card=CreditCard(
                id=0,
                name="Visa",
                credit_limit=Amount(pence=100000),
                current_balance_used=Amount(pence=0),
            )
        )
        budget_service.add_bill(bill=_bill("Sub", 9999, 27, method=card.id))
        budget_service.add_income(income=_income("Bonus", 20000, 30))

        projection, _ = budget_service._build_safe_to_spend_inputs(_TODAY)
        assert projection[0].day == _TODAY
        total_days = days_in_month(2026, 7)
        remaining_food = prorate_remaining_pence(31000, _TODAY.day, total_days)
        expected_close = 100000 + 20000 - 5000 - remaining_food
        july_close = next(d for d in projection if d.day == date(2026, 7, total_days))
        assert july_close.balance_pence == expected_close
        # August then opens exactly where July closed.
        aug_first = next(d for d in projection if d.day == date(2026, 8, 1))
        assert aug_first.day - july_close.day == timedelta(days=1)

    def test_determinism_two_identical_calls_agree(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=90000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 150000, 1))
        budget_service.add_bill(bill=_bill("Water", 12345, 28))
        first = budget_service.get_safe_to_spend(today=_TODAY)
        second = budget_service.get_safe_to_spend(today=_TODAY)
        assert first == second
