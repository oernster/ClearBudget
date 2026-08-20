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
def make_service(tmp_path):
    """Build a BudgetService on a database of its own.

    A factory rather than a single service, because the assumption is no
    longer switchable: showing that repeating this month forward CHANGES
    something means comparing two real budgets, one with the ad hoc income
    and one without, rather than reading one budget two ways.
    """
    created = []

    def _make(name: str = "test") -> BudgetService:
        db = Database(tmp_path / f"{name}.db")
        db.connect()
        db.create_schema()
        created.append(db)
        return BudgetService(
            bill_repo=SQLiteBillRepository(db.conn),
            income_repo=SQLiteIncomeSourceRepository(db.conn),
            payment_method_repo=SQLitePaymentMethodRepository(db.conn),
            month_generator=MonthGenerator(
                SQLiteBillRepository(db.conn), SQLiteIncomeSourceRepository(db.conn)
            ),
        )

    yield _make
    for db in created:
        db.close()


@pytest.fixture()
def service(make_service):
    """BudgetService wired to a temp SQLite database."""
    return make_service()


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


def _bare_months(service) -> None:
    """The same budget with no ad hoc income entered in any month.

    The baseline the repeated shape is measured against, now that there is no
    second reading to compare a budget with itself.
    """
    _seed_balance(service.bill_repo.conn, pence=0, iso="2026-07-01")
    service.set_safe_to_spend_floor(amount=Amount(pence=0))
    service.add_income(income=_income("Salary", 100000, 10))
    service.add_bill(bill=_bill("Rent", 130000, 5))


def _august_movement(service) -> int:
    """What August does to the balance, from its opening to its close."""
    by_day = {
        d.day: d.balance_pence for d in service._build_safe_to_spend_inputs(_TODAY)
    }
    return by_day[date(2026, 8, 31)] - by_day[date(2026, 7, 31)]


class TestTheRepeatedShape:
    def test_a_month_lacking_this_month_s_extra_receives_it(
        self, service, make_service
    ):
        _thin_months(service)
        bare = make_service("bare")
        _bare_months(bare)
        # Measured on August's own movement rather than its close, so July's
        # top-up cannot leak into the comparison: August gains exactly one.
        assert _august_movement(service) - _august_movement(bare) == 60000

    def test_the_top_up_lands_on_the_day_it_falls_on_in_this_month(self, service):
        _thin_months(service)
        projection = service._build_safe_to_spend_inputs(_TODAY)
        by_day = {d.day: d.balance_pence for d in projection}
        # Entered for day 12, so day 12 is where August's balance steps up.
        step = by_day[date(2026, 8, 12)] - by_day[date(2026, 8, 11)]
        assert step == 60000

    def test_the_recurring_salary_is_never_counted_twice(self, service):
        _thin_months(service)
        projection = service._build_safe_to_spend_inputs(_TODAY)
        by_day = {d.day: d.balance_pence for d in projection}
        assert by_day[date(2026, 8, 10)] - by_day[date(2026, 8, 9)] == 100000

    def test_a_month_that_already_has_the_entry_gains_nothing(self, service):
        _thin_months(service)
        service.add_income_month_extra(
            income=_income("Family top-up", 60000, 12), year_month=_AUGUST
        )
        projection = service._build_safe_to_spend_inputs(_TODAY)
        by_day = {d.day: d.balance_pence for d in projection}
        # August has its own entry, so day 12 steps up by one top-up and not
        # by two: the fill only ever covers a gap.
        assert by_day[date(2026, 8, 12)] - by_day[date(2026, 8, 11)] == 60000

    def test_matching_ignores_case_and_surrounding_space(self, service):
        _thin_months(service)
        service.add_income_month_extra(
            income=_income("  FAMILY TOP-UP ", 60000, 12), year_month=_AUGUST
        )
        projection = service._build_safe_to_spend_inputs(_TODAY)
        by_day = {d.day: d.balance_pence for d in projection}
        # Recognised as the same money despite the case and the spaces, so
        # the fill stays away and day 12 steps up once.
        assert by_day[date(2026, 8, 12)] - by_day[date(2026, 8, 11)] == 60000

    def test_an_undated_top_up_lands_on_the_first_of_the_month(self, service):
        """An income with no day is carried at the undated day, never dropped."""
        _seed_balance(service.bill_repo.conn, pence=0, iso="2026-07-01")
        service.add_income(income=_income("Salary", 100000, 10))
        service.add_income_month_extra(
            income=_income("Bonus", 25000, None), year_month=_JULY
        )
        projection = service._build_safe_to_spend_inputs(_TODAY)
        by_day = {d.day: d.balance_pence for d in projection}
        # No rent in this budget, so the whole step into August is the bonus.
        assert by_day[date(2026, 8, 1)] - by_day[date(2026, 7, 31)] == 25000


class TestTheSpendableFigure:
    def test_repeating_this_month_shrinks_the_shortfall(self, service, make_service):
        """Both bases share a headline here, because THIS month is the one under.

        The difference the assumption makes therefore shows up in the gap
        beyond it, which is exactly where it should: repeating the income
        cannot rescue a month that has already happened.
        """
        _thin_months(service)
        bare = make_service("bare")
        _bare_months(bare)
        with_top_up = service.get_safe_to_spend(today=_TODAY)
        without = bare.get_safe_to_spend(today=_TODAY)
        assert without.amount_pence < 0
        assert without.has_shortfall
        assert with_top_up.shortfall_pence < without.shortfall_pence

    def test_the_gap_beyond_moves_nearer_once_the_later_months_survive(
        self, service, make_service
    ):
        """The counterintuitive direction, pinned.

        Filling the later months moves the surviving edge, so the first month
        that still cannot be saved moves TOWARD today rather than away. Read
        without that in mind, an assumed reading that is not simply better
        everywhere looks like a fault.
        """
        _thin_months(service)
        bare = make_service("bare")
        _bare_months(bare)
        with_top_up = service.get_safe_to_spend(today=_TODAY)
        without = bare.get_safe_to_spend(today=_TODAY)
        assert with_top_up.shortfall_day < without.shortfall_day

    def test_the_capacity_schedule_reads_the_same_projection(self, service):
        _thin_months(service)
        steps = service.get_spending_capacity(today=_TODAY)
        headline = service.get_safe_to_spend(today=_TODAY)
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


class TestAssumedMonthSummary:
    """The assumption stated as a month, for the projection page's narrative.

    The page shows a spendable figure and a month-by-month projection on one
    assumption, so both have to be built from one statement of it. These pin
    the summary to the same fill-forward rule the per-day projection uses.
    """

    def test_a_later_month_gains_this_month_s_extra(self, service):
        _thin_months(service)
        assumed = service.get_assumed_month_summary(year_month=_AUGUST, today=_TODAY)
        known = service.get_month_summary(year_month=_AUGUST)
        assert assumed.total_income.pence - known.total_income.pence == 60000
        assert "Family top-up" in [s.name for s in assumed.income_sources]

    def test_the_month_keeps_its_own_bills(self, service):
        _thin_months(service)
        assumed = service.get_assumed_month_summary(year_month=_AUGUST, today=_TODAY)
        known = service.get_month_summary(year_month=_AUGUST)
        assert assumed.bills == known.bills
        assert assumed.bank_bills == known.bank_bills

    def test_the_balance_follows_the_filled_income(self, service):
        _thin_months(service)
        assumed = service.get_assumed_month_summary(year_month=_AUGUST, today=_TODAY)
        assert (
            assumed.balance.pence
            == assumed.total_income.pence - assumed.bank_bills.pence
        )

    def test_a_month_whose_income_never_covers_its_bills_floors_at_zero(self, service):
        _seed_balance(service.bill_repo.conn, pence=0, iso="2026-07-01")
        service.add_income(income=_income("Salary", 10000, 10))
        service.add_bill(bill=_bill("Rent", 130000, 5))
        service.add_income_month_extra(
            income=_income("Family top-up", 5000, 12), year_month=_JULY
        )
        assumed = service.get_assumed_month_summary(year_month=_AUGUST, today=_TODAY)
        assert assumed.balance.pence == 0

    def test_a_month_that_already_has_the_entry_gains_nothing(self, service):
        _thin_months(service)
        service.add_income_month_extra(
            income=_income("Family top-up", 60000, 12), year_month=_AUGUST
        )
        assumed = service.get_assumed_month_summary(year_month=_AUGUST, today=_TODAY)
        assert assumed == service.get_month_summary(
            year_month=_AUGUST, include_assumed=True
        )

    def test_the_current_month_is_never_filled_from_itself(self, service):
        _thin_months(service)
        assumed = service.get_assumed_month_summary(year_month=_JULY, today=_TODAY)
        assert assumed == service.get_month_summary(
            year_month=_JULY, include_assumed=True
        )

    def test_a_past_month_is_left_alone(self, service):
        # An earlier month has nothing to receive: the income repeats forward.
        _thin_months(service)
        june = YearMonth(2026, 6)
        assumed = service.get_assumed_month_summary(year_month=june, today=_TODAY)
        assert assumed == service.get_month_summary(
            year_month=june, include_assumed=True
        )

    def test_it_agrees_with_the_per_day_projection_about_the_same_month(self, service):
        # The point of the method: the narrative and the spendable figure are
        # one assumption read twice, so August's shape has to be the same in
        # both. A divergence here would put two answers on one page.
        _thin_months(service)
        assumed = service.get_assumed_month_summary(year_month=_AUGUST, today=_TODAY)
        projection = service._build_safe_to_spend_inputs(_TODAY)
        by_day = {d.day: d.balance_pence for d in projection}
        movement = by_day[date(2026, 8, 31)] - by_day[date(2026, 7, 31)]
        assert movement == assumed.total_income.pence - assumed.bank_bills.pence
