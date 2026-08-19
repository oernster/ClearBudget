"""Tests for the safe-to-spend adapter and settings on BudgetService."""

from datetime import date

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.services.safe_to_spend import SustainableResult
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
    def test_buffer_defaults_to_twenty_and_round_trips(self, budget_service):
        assert budget_service.get_safe_to_spend_floor() == Amount(pence=2000)
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=10000))
        assert budget_service.get_safe_to_spend_floor() == Amount(pence=10000)

    def test_an_explicit_zero_buffer_is_honoured_not_defaulted(self, budget_service):
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        assert budget_service.get_safe_to_spend_floor() == Amount(pence=0)

    def test_the_window_defaults_to_four_months_and_round_trips(self, budget_service):
        assert budget_service.get_sustainable_window_months() == 4
        budget_service.set_sustainable_window_months(months=2)
        assert budget_service.get_sustainable_window_months() == 2


class TestSpendingCapacity:
    def test_the_first_step_repeats_the_headline(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 200000, 28))
        budget_service.add_bill(bill=_bill("Water", 30000, 27))
        steps = budget_service.get_spending_capacity(today=_TODAY)
        headline = budget_service.get_safe_to_spend(today=_TODAY)
        assert steps[0].from_day == _TODAY
        assert steps[0].amount_pence == headline.amount_pence
        assert steps[0].binding_day == headline.binding_day

    def test_waiting_past_the_low_day_raises_the_figure(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=50000, iso="2026-07-26")
        # The bill on the 27th is the low; the salary on the 28th lifts it.
        budget_service.add_bill(bill=_bill("Water", 40000, 27))
        budget_service.add_income(income=_income("Salary", 200000, 28))
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        steps = budget_service.get_spending_capacity(today=_TODAY)
        assert [s.amount_pence for s in steps] == sorted(s.amount_pence for s in steps)
        assert steps[0].amount_pence == 10000
        assert steps[-1].from_day > steps[0].from_day
        assert steps[-1].amount_pence > steps[0].amount_pence

    def test_a_flat_month_reports_a_single_step(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        # Nothing lands and nothing leaves before month end, so the figure
        # never moves and there is nothing to report beyond the headline.
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        steps = budget_service.get_spending_capacity(today=_TODAY)
        assert len(steps) == 1
        assert steps[0].from_day == _TODAY

    def test_steps_never_leave_the_current_month(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 200000, 28))
        steps = budget_service.get_spending_capacity(today=_TODAY)
        assert all(s.from_day.month == _JULY.month for s in steps)
        assert all(s.from_day.year == _JULY.year for s in steps)

    def test_a_later_month_still_holds_every_step_down(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=50000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 200000, 28))
        # A big August bill outlives the July salary, so once the July low is
        # behind, the figure is set outside this month: waiting stops helping
        # because the constraint has moved to a month waiting cannot reach.
        budget_service.add_bill(bill=_bill("Insurance", 190000, 15, start=_AUGUST))
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        steps = budget_service.get_spending_capacity(today=_TODAY)
        assert steps[-1].binding_day.month == _AUGUST.month
        # And the August constraint caps it: the July salary is 200000 while
        # the step it buys is worth far less than that.
        assert steps[-1].amount_pence == 60000


class TestSustainableHeadline:
    def test_a_later_month_that_collapses_is_named_not_netted_off(self, budget_service):
        """A collapse ahead is a shortfall, not a limit on today.

        Letting it drive the headline reported nothing spendable while this
        month still had real headroom, which answers "does my budget hold" in
        the slot reserved for "what can I spend". The collapse is reported on
        its own terms instead, so neither fact is lost.
        """
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 50000, 1))
        budget_service.add_bill(bill=_bill("Rent", 190000, 10, start=_AUGUST))
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        result = budget_service.get_safe_to_spend(today=_TODAY)
        assert result.is_sustainable
        assert result.amount_pence == 100000
        assert result.covered_end.month == _TODAY.month
        assert result.has_shortfall
        assert result.shortfall_day > result.covered_end

    def test_a_window_that_holds_reports_what_it_can_spare(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 300000, 1))
        budget_service.add_bill(bill=_bill("Rent", 50000, 10))
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        result = budget_service.get_safe_to_spend(today=_TODAY)
        assert result.is_sustainable
        assert result.amount_pence > 0

    def test_a_longer_window_never_offers_more_only_sees_further(self, budget_service):
        """A longer window is a harder promise, so it can never allow more.

        It can allow the SAME, which is the case here: the extra months
        cannot be promised, so they change what is reported about the
        shortfall rather than what is offered for today.
        """
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 50000, 1))
        budget_service.add_bill(bill=_bill("Rent", 190000, 10, start=_AUGUST))
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        budget_service.set_sustainable_window_months(months=1)
        short = budget_service.get_safe_to_spend(today=_TODAY)
        budget_service.set_sustainable_window_months(months=4)
        long = budget_service.get_safe_to_spend(today=_TODAY)
        assert long.amount_pence <= short.amount_pence
        assert long.has_shortfall
        assert not short.has_shortfall

    def test_the_default_today_is_the_real_one(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=90000, iso="2026-07-26")
        budget_service.add_income(income=_income("Salary", 150000, 1))
        assert isinstance(budget_service.get_safe_to_spend(), SustainableResult)


class TestWhatTheProjectionCounts:
    def test_income_already_received_is_not_counted_again(self, budget_service):
        """It is already inside the stored balance."""
        _seed_balance(budget_service.bill_repo.conn, pence=60000, iso="2026-07-26")
        bonus = budget_service.add_income(income=_income("Bonus", 20000, 28))
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        before = budget_service.get_safe_to_spend(today=_TODAY).amount_pence
        budget_service.mark_income_received_for_month(
            income_id=bonus.id, year_month=_JULY
        )
        after = budget_service.get_safe_to_spend(today=_TODAY).amount_pence
        assert after <= before

    def test_a_card_bill_never_touches_the_bank_projection(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=60000, iso="2026-07-26")
        budget_service.set_safe_to_spend_floor(amount=Amount(pence=0))
        before = budget_service.get_safe_to_spend(today=_TODAY).amount_pence
        budget_service.add_bill(bill=_bill("Streaming", 5000, 28, method=2))
        after = budget_service.get_safe_to_spend(today=_TODAY).amount_pence
        assert after == before
