"""The second reading assumes this month repeats, rather than waiting to be told.

The old assumption keyed off a per-item "reliable" tick, so it stayed invisible
until the user marked something. The derived one takes any income entered for
the current month to arrive again in every later month with no entry of that
name, which is exactly the shape of a budget kept month by month: the recurring
sources are already in every month, so what repeats forward is the ad hoc money
that has only been typed in where it has already happened.

These run against a real SQLite database, because the distinction that matters
(a recurring source appears in every month, a one-off appears in one) is a
storage fact rather than a calculation.
"""

from datetime import date

import pytest

from clear_budget.application.projection_basis import ProjectionBasis
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
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

_TODAY = date(2026, 7, 1)
_JULY = YearMonth(2026, 7)
_AUGUST = YearMonth(2026, 8)
_SEPTEMBER = YearMonth(2026, 9)


@pytest.fixture()
def service(tmp_path):
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


def _income(name: str, pence: int, day, *, reliable: bool = True) -> IncomeSource:
    return IncomeSource(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        is_reliable=reliable,
        day_of_month=day,
    )


def _bill(name: str, pence: int, day) -> Bill:
    return Bill(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        payment_method_id=1,
        category="utilities",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
        target_card_id=None,
    )


def _thin_months(service) -> None:
    """A recurring salary in every month; a top-up entered for July alone."""
    _seed_balance(service.bill_repo.conn, pence=0, iso="2026-07-01")
    service.set_safe_to_spend_floor(amount=Amount(pence=0))
    service.add_income(income=_income("Salary", 100000, 10))
    service.add_bill(bill=_bill("Rent", 130000, 5))
    service.add_income_month_extra(
        income=_income("Family top-up", 60000, 12), year_month=_JULY
    )


class TestTheRepeatedShape:
    def test_a_month_lacking_this_month_s_extra_receives_it(self, service):
        _thin_months(service)
        known = service._build_safe_to_spend_inputs(_TODAY)
        repeated = service._build_safe_to_spend_inputs(
            _TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        end_of_august = date(2026, 8, 31)
        known_close = next(d.balance_pence for d in known if d.day == end_of_august)
        repeat_close = next(d.balance_pence for d in repeated if d.day == end_of_august)
        # July is identical under both; August gains exactly the one top-up.
        assert repeat_close - known_close == 60000

    def test_the_top_up_lands_on_the_day_it_falls_on_in_this_month(self, service):
        _thin_months(service)
        repeated = service._build_safe_to_spend_inputs(
            _TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        by_day = {d.day: d.balance_pence for d in repeated}
        # Entered for day 12, so day 12 is where August's balance steps up.
        step = by_day[date(2026, 8, 12)] - by_day[date(2026, 8, 11)]
        assert step == 60000

    def test_the_recurring_salary_is_never_counted_twice(self, service):
        _thin_months(service)
        repeated = service._build_safe_to_spend_inputs(
            _TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        by_day = {d.day: d.balance_pence for d in repeated}
        assert by_day[date(2026, 8, 10)] - by_day[date(2026, 8, 9)] == 100000

    def test_a_month_that_already_has_the_entry_gains_nothing(self, service):
        _thin_months(service)
        service.add_income_month_extra(
            income=_income("Family top-up", 60000, 12), year_month=_AUGUST
        )
        known = service._build_safe_to_spend_inputs(_TODAY)
        repeated = service._build_safe_to_spend_inputs(
            _TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        end_of_august = date(2026, 8, 31)
        known_close = next(d.balance_pence for d in known if d.day == end_of_august)
        repeat_close = next(d.balance_pence for d in repeated if d.day == end_of_august)
        assert repeat_close == known_close

    def test_matching_ignores_case_and_surrounding_space(self, service):
        _thin_months(service)
        service.add_income_month_extra(
            income=_income("  FAMILY TOP-UP ", 60000, 12), year_month=_AUGUST
        )
        known = service._build_safe_to_spend_inputs(_TODAY)
        repeated = service._build_safe_to_spend_inputs(
            _TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        end_of_august = date(2026, 8, 31)
        known_close = next(d.balance_pence for d in known if d.day == end_of_august)
        repeat_close = next(d.balance_pence for d in repeated if d.day == end_of_august)
        assert repeat_close == known_close

    def test_an_undated_top_up_lands_on_the_first_of_the_month(self, service):
        """An income with no day is carried at the undated day, never dropped."""
        _seed_balance(service.bill_repo.conn, pence=0, iso="2026-07-01")
        service.add_income(income=_income("Salary", 100000, 10))
        service.add_income_month_extra(
            income=_income("Bonus", 25000, None), year_month=_JULY
        )
        known = service._build_safe_to_spend_inputs(_TODAY)
        repeated = service._build_safe_to_spend_inputs(
            _TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        first = date(2026, 8, 1)
        known_first = next(d.balance_pence for d in known if d.day == first)
        repeat_first = next(d.balance_pence for d in repeated if d.day == first)
        assert repeat_first - known_first == 25000

    def test_the_known_basis_repeats_nothing(self, service):
        _thin_months(service)
        default = service._build_safe_to_spend_inputs(_TODAY)
        explicit = service._build_safe_to_spend_inputs(
            _TODAY, basis=ProjectionBasis.KNOWN
        )
        assert [d.balance_pence for d in default] == [d.balance_pence for d in explicit]


class TestTheSpendableFigure:
    def test_repeating_this_month_shrinks_the_shortfall(self, service):
        _thin_months(service)
        known = service.get_safe_to_spend(today=_TODAY)
        repeated = service.get_safe_to_spend(
            today=_TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        assert known.amount_pence < 0
        assert repeated.amount_pence > known.amount_pence

    def test_the_constraint_moves_nearer_once_the_later_months_survive(self, service):
        """The counterintuitive direction, pinned.

        Filling the later months stops them being the thing that binds, so the
        binding day moves TOWARD today rather than away. Read without that in
        mind, an assumed figure that is not simply larger looks like a fault.
        """
        _thin_months(service)
        known = service.get_safe_to_spend(today=_TODAY)
        repeated = service.get_safe_to_spend(
            today=_TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        assert repeated.binding_day < known.binding_day

    def test_the_capacity_schedule_reads_the_same_basis(self, service):
        _thin_months(service)
        steps = service.get_spending_capacity(
            today=_TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        headline = service.get_safe_to_spend(
            today=_TODAY, basis=ProjectionBasis.REPEAT_CURRENT
        )
        assert steps[0].amount_pence == headline.amount_pence


class TestWhatTheAssumptionRestsOn:
    def test_a_repeated_top_up_is_named_for_each_month_that_lacks_it(self, service):
        _thin_months(service)
        expected = service.get_assumed_expectations(today=_TODAY)
        months = [month for month, _ in expected]
        assert _JULY not in months
        assert _AUGUST in months
        assert _SEPTEMBER in months
        assert {source.name for _, source in expected} == {"Family top-up"}

    def test_it_spans_the_sustainable_window_and_no_further(self, service):
        _thin_months(service)
        service.set_sustainable_window_months(months=2)
        expected = service.get_assumed_expectations(today=_TODAY)
        assert [month for month, _ in expected] == [_AUGUST]

    def test_income_marked_unreliable_is_still_named(self, service):
        _seed_balance(service.bill_repo.conn, pence=0, iso="2026-07-01")
        service.add_income(income=_income("Maybe work", 40000, 15, reliable=False))
        expected = service.get_assumed_expectations(today=_TODAY)
        assert (_JULY, "Maybe work") in [(m, s.name) for m, s in expected]

    def test_a_budget_whose_months_all_match_expects_nothing(self, service):
        _seed_balance(service.bill_repo.conn, pence=0, iso="2026-07-01")
        service.add_income(income=_income("Salary", 100000, 10))
        service.add_bill(bill=_bill("Rent", 50000, 5))
        assert service.get_assumed_expectations(today=_TODAY) == ()

    def test_an_unreliable_income_is_never_listed_twice_for_one_month(self, service):
        _seed_balance(service.bill_repo.conn, pence=0, iso="2026-07-01")
        service.add_income(income=_income("Maybe work", 40000, 15, reliable=False))
        expected = service.get_assumed_expectations(today=_TODAY)
        august = [source.name for month, source in expected if month == _AUGUST]
        assert august.count("Maybe work") <= 1
