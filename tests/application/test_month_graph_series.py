"""Tests for the month graph day-by-day balance series."""

from datetime import date

import pytest

from clear_budget.application.services._card_projection import card_openings_at
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
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

_TODAY = date(2026, 7, 26)
_JULY = YearMonth(2026, 7)
_AUGUST = YearMonth(2026, 8)
_SEPTEMBER = YearMonth(2026, 9)
_OCTOBER = YearMonth(2026, 10)


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
    name: str,
    pence: int,
    day,
    *,
    method: int = 1,
    start: YearMonth | None = None,
    category: str = "utilities",
    target_card_id: int | None = None,
) -> Bill:
    return Bill(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        payment_method_id=method,
        category=category,
        bill_type="fixed",
        day_of_month=day,
        start_ym=start or YearMonth(2026, 1),
        end_ym=None,
        target_card_id=target_card_id,
    )


def _income(name: str, pence: int, day) -> IncomeSource:
    return IncomeSource(
        id=0, name=name, amount=Amount(pence=pence), is_reliable=True, day_of_month=day
    )


def _bank_series(svc, year_month):
    summary = svc.get_month_summary(year_month=year_month)
    return svc.get_bank_graph_series(
        year_month=year_month, summary=summary, today=_TODAY
    )


class TestBankGraphSeries:
    def test_future_month_starts_from_projected_opening(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.add_bill(bill=_bill("Rent", 5000, 10, start=_AUGUST))
        budget_service.add_income(income=_income("Salary", 20000, 1))
        series = _bank_series(budget_service, _AUGUST)
        assert len(series.values) == 31
        assert series.values[0] == 120000  # salary lands day 1
        assert series.values[8] == 120000  # day 9, rent not yet due
        assert series.values[9] == 115000  # rent taken day 10
        assert series.values[30] == 115000

    def test_current_month_passes_through_todays_balance(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        salary = budget_service.add_income(income=_income("Salary", 20000, 5))
        # Marked Received, as the midnight fold leaves a landed income:
        # whether something happened is read from the flag, not from its day.
        budget_service.mark_income_received_for_month(
            income_id=salary.id, year_month=_JULY
        )
        budget_service.add_bill(bill=_bill("Water", 5000, 28))
        series = _bank_series(budget_service, _JULY)
        assert len(series.values) == 31
        assert series.values[3] == 80000  # day 4, before salary
        assert series.values[25] == 100000  # day 26 (today) = stored balance
        assert series.values[27] == 95000  # day 28, water taken
        assert series.label == "Bank balance"

    def test_undated_items_use_projection_day_conventions(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=50000, iso="2026-07-26")
        budget_service.add_income(income=_income("Odd jobs", 10000, None))
        budget_service.add_bill(bill=_bill("Food", 20000, None, start=_AUGUST))
        series = _bank_series(budget_service, _AUGUST)
        # Undated income lands day 1; the undated bill is taken near month end.
        assert series.values[0] == series.values[26]
        assert series.values[27] == series.values[26] - 20000

    def test_default_today_argument(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=50000, iso="2026-07-26")
        summary = budget_service.get_month_summary(year_month=_JULY)
        series = budget_service.get_bank_graph_series(year_month=_JULY, summary=summary)
        assert len(series.values) == 31

    def test_card_bills_never_touch_the_bank_series(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=50000, iso="2026-07-26")
        card = budget_service.payment_method_repo.add_credit_card(
            card=CreditCard(
                id=0,
                name="Visa",
                credit_limit=Amount(pence=100000),
                current_balance_used=Amount(pence=0),
            )
        )
        budget_service.add_bill(bill=_bill("Sub", 12345, 10, method=card.id))
        series = _bank_series(budget_service, _JULY)
        assert all(value == 50000 for value in series.values)

    def test_a_bill_paid_early_is_not_charged_again(self, budget_service):
        """A bill marked Paid before its due day is already inside the stored
        balance, so the graph must not take it again when the day arrives."""
        _seed_balance(budget_service.bill_repo.conn, pence=34282, iso="2026-07-26")
        rent = budget_service.add_bill(bill=_bill("Rent", 135000, 28))
        budget_service.mark_bill_paid_for_month(bill_id=rent.id, year_month=_JULY)
        series = _bank_series(budget_service, _JULY)
        assert series.values[25] == 34282  # today passes through stored balance
        assert series.values[27] == 34282  # the due day takes nothing twice
        assert series.values[30] == 34282

    def test_a_bill_paid_on_a_past_day_still_shows_its_drop(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        water = budget_service.add_bill(bill=_bill("Water", 5000, 5))
        budget_service.mark_bill_paid_for_month(bill_id=water.id, year_month=_JULY)
        series = _bank_series(budget_service, _JULY)
        assert series.values[3] == 105000  # before the due day
        assert series.values[5] == 100000  # taken on day 5, as it really was
        assert series.values[25] == 100000  # anchor still holds

    def test_income_received_early_is_not_added_again(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=60000, iso="2026-07-26")
        bonus = budget_service.add_income(income=_income("Bonus", 20000, 30))
        budget_service.mark_income_received_for_month(
            income_id=bonus.id, year_month=_JULY
        )
        series = _bank_series(budget_service, _JULY)
        assert series.values[25] == 60000
        assert series.values[29] == 60000  # day 30 adds nothing twice

    def test_an_overdue_unpaid_bill_draws_no_phantom_history(self, budget_service):
        """A dated bill that never got paid took no money on its day, so the
        historical stretch of the curve must not show a drop for it, exactly
        as the projected-balance rule already excludes it from still-due."""
        _seed_balance(budget_service.bill_repo.conn, pence=40000, iso="2026-07-26")
        budget_service.add_bill(bill=_bill("Missed", 10000, 4))
        series = _bank_series(budget_service, _JULY)
        assert series.values[0] == 40000
        assert series.values[3] == 40000
        assert series.values[25] == 40000


class TestCardGraphSeries:
    def _add_card(self, svc, name: str, used: int) -> CreditCard:
        card = CreditCard(
            id=0,
            name=name,
            credit_limit=Amount(pence=500000),
            current_balance_used=Amount(pence=used),
        )
        return svc.payment_method_repo.add_credit_card(card=card)

    def test_card_series_tracks_charges_and_payments(self, budget_service):
        card = self._add_card(budget_service, "Visa", 10000)
        budget_service.add_bill(bill=_bill("Sub", 3000, 10, method=card.id))
        budget_service.add_bill(
            bill=_bill(
                "Visa payment",
                2000,
                20,
                category="credit_payment",
                target_card_id=card.id,
            )
        )
        series = budget_service.get_card_graph_series(year_month=_AUGUST)
        assert [s.label for s in series] == ["Visa"]
        values = series[0].values
        assert len(values) == 31
        assert values[0] == 10000
        assert values[9] == 13000  # charge lands day 10
        assert values[19] == 11000  # payment lands day 20
        assert values[30] == 11000

    def test_card_balance_never_goes_negative(self, budget_service):
        card = self._add_card(budget_service, "Visa", 1000)
        budget_service.add_bill(
            bill=_bill(
                "Big payment",
                50000,
                5,
                category="credit_payment",
                target_card_id=card.id,
            )
        )
        series = budget_service.get_card_graph_series(year_month=_AUGUST)
        assert series[0].values[10] == 0

    def test_no_cards_means_no_series(self, budget_service):
        assert budget_service.get_card_graph_series(year_month=_AUGUST) == []


def _chained_card(svc, name: str, used: int, apr: float | None = None) -> CreditCard:
    card = CreditCard(
        id=0,
        name=name,
        credit_limit=Amount(pence=500000),
        current_balance_used=Amount(pence=used),
        interest_rate_apr=apr,
    )
    return svc.payment_method_repo.add_credit_card(card=card)


class TestCardGraphChaining:
    """A future month's card series opens from the chained projection.

    The stored balance is as-of the day it was entered, so opening a distant
    month from it drew a balance untouched by every intervening payment and
    every month's interest: May 2028 showed the card where it stood today.
    """

    def test_a_future_month_opens_from_the_chained_projection(self, budget_service):
        card = _chained_card(budget_service, "Visa", 100000)
        budget_service.add_bill(
            bill=_bill(
                "Visa payment",
                10000,
                20,
                category="credit_payment",
                target_card_id=card.id,
            )
        )
        values = budget_service.get_card_graph_series(
            year_month=_OCTOBER, today=_TODAY
        )[0].values
        # July, August and September each pay 10000 off before October opens.
        assert values[0] == 70000
        assert values[18] == 70000
        assert values[19] == 60000  # October's own payment lands day 20
        assert values[30] == 60000

    def test_a_month_closes_where_the_next_one_opens(self, budget_service):
        card = _chained_card(budget_service, "Visa", 100000, apr=12.0)
        assert card.interest_rate_apr == 12.0
        september = budget_service.get_card_graph_series(
            year_month=_SEPTEMBER, today=_TODAY
        )[0].values
        october = budget_service.get_card_graph_series(
            year_month=_OCTOBER, today=_TODAY
        )[0].values
        # 1% a month: July closes 101000, August 102010; September opens there.
        assert september[0] == 102010
        assert september[-2] == 102010  # no interest until the month ends
        assert september[-1] == 103030  # the month's interest lands on its last day
        assert october[0] == 103030  # and the next month opens exactly there

    def test_the_current_month_still_opens_from_the_anchored_balance(
        self, budget_service
    ):
        _chained_card(budget_service, "Visa", 45000)
        values = budget_service.get_card_graph_series(year_month=_JULY, today=_TODAY)[
            0
        ].values
        assert values[0] == 45000

    def test_openings_for_the_current_month_are_the_anchored_opening(
        self, budget_service
    ):
        card = _chained_card(budget_service, "Visa", 12345)
        openings = card_openings_at(
            budget_service.payment_method_repo,
            budget_service.get_month_summary,
            month=_JULY,
            today_ym=_JULY,
        )
        assert openings == {card.id: 12345}

    def test_no_cards_yields_no_openings(self, budget_service):
        openings = card_openings_at(
            budget_service.payment_method_repo,
            budget_service.get_month_summary,
            month=_OCTOBER,
            today_ym=_JULY,
        )
        assert openings == {}
