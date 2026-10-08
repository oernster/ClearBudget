"""Tests for the month graph's day-by-day bank balance series."""

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from tests.application._graph_support import (
    _AUGUST,
    _JULY,
    _TODAY,
    _bill,
    _income,
    _seed_balance,
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

    def test_income_received_early_is_not_carried_into_next_month(self, budget_service):
        """Next month opens where this month closes. Income marked Received
        before its due day is already inside the stored balance, so carrying
        it forward again would open next month too high by its amount; one
        still to come is carried as before."""
        _seed_balance(budget_service.bill_repo.conn, pence=60000, iso="2026-07-26")
        early = budget_service.add_income(income=_income("Early", 20000, 30))
        budget_service.add_income(income=_income("Pending", 7000, 29))
        rent = budget_service.add_bill(bill=_bill("Rent", 10000, 28))
        budget_service.mark_income_received_for_month(
            income_id=early.id, year_month=_JULY
        )
        budget_service.mark_bill_paid_for_month(bill_id=rent.id, year_month=_JULY)
        july_close = _bank_series(budget_service, _JULY).values[-1]
        august = budget_service.get_month_summary(year_month=_AUGUST)
        august_open = budget_service.get_bank_month_opening_pence(
            year_month=_AUGUST, summary=august, today=_TODAY
        )
        assert july_close == 67000
        assert august_open == july_close

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
