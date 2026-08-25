"""Tests for the one month-walk both the bank page and Reserves read.

It lived in the Solvency panel until two pages needed it, where the coverage
gate could not see it. The card-bill branch below had never been measured at
all: a card bill must not move the BANK balance, yet nothing asserted it.
"""

from types import SimpleNamespace

from clear_budget.application.services._month_walk import LOW_AT_START, walk_month

_BANK = 1
_CARD = 2
_OPENING_PENCE = 100000


def _income(pence, day=None):
    return SimpleNamespace(
        amount=SimpleNamespace(pence=pence), day_of_month=day, name="pay"
    )


def _bill(pence, day=None, method=_BANK, name="bill"):
    return SimpleNamespace(
        amount=SimpleNamespace(pence=pence),
        day_of_month=day,
        payment_method_id=method,
        name=name,
    )


def _summary(bills=(), incomes=()):
    return SimpleNamespace(bills=tuple(bills), income_sources=tuple(incomes))


def _walk(bills=(), incomes=(), opening=_OPENING_PENCE):
    return walk_month(opening, _summary(bills, incomes))


class TestWhatMovesTheBalance:
    def test_a_bank_bill_takes_money_out(self):
        assert _walk(bills=[_bill(30000, 5)])["closing"] == _OPENING_PENCE - 30000

    def test_income_puts_money_in(self):
        assert _walk(incomes=[_income(30000, 5)])["closing"] == _OPENING_PENCE + 30000

    def test_a_card_bill_leaves_the_bank_balance_alone(self):
        """It is paid from the card, so the bank never sees it."""
        assert _walk(bills=[_bill(30000, 5, method=_CARD)])["closing"] == _OPENING_PENCE

    def test_a_card_bill_cannot_create_a_low(self):
        walk = _walk(bills=[_bill(999999, 5, method=_CARD)])
        assert walk["min_balance"] == _OPENING_PENCE
        assert walk["min_day"] == LOW_AT_START

    def test_bank_and_card_bills_together_count_only_the_bank_one(self):
        both = _walk(bills=[_bill(30000, 5), _bill(50000, 6, method=_CARD)])
        assert both["closing"] == _OPENING_PENCE - 30000


class TestTheLow:
    def test_a_month_that_never_dips_lows_at_its_opening(self):
        walk = _walk(incomes=[_income(10000, 5)])
        assert walk["min_balance"] == _OPENING_PENCE
        assert walk["min_day"] == LOW_AT_START

    def test_the_low_names_the_day_it_fell_on(self):
        walk = _walk(bills=[_bill(30000, 12)])
        assert walk["min_day"] == 12

    def test_income_lands_before_bills_on_a_shared_day(self):
        """The optimistic ordering: money is received before payments go."""
        walk = _walk(bills=[_bill(120000, 10)], incomes=[_income(50000, 10)])
        assert walk["min_balance"] == _OPENING_PENCE + 50000 - 120000

    def test_an_undated_income_arrives_at_the_start(self):
        walk = _walk(bills=[_bill(120000, 2)], incomes=[_income(50000)])
        assert walk["min_balance"] == _OPENING_PENCE + 50000 - 120000

    def test_an_undated_bill_goes_late_in_the_month(self):
        """The cautious reading: it leaves no later than it might."""
        walk = _walk(bills=[_bill(200000)], incomes=[_income(50000, 27)])
        assert walk["min_day"] == 28


class TestGoingUnder:
    def test_it_names_the_first_day_below_zero(self):
        walk = _walk(bills=[_bill(150000, 4)])
        assert walk["first_negative_day"] == 4

    def test_a_month_that_stays_positive_names_no_such_day(self):
        assert _walk(bills=[_bill(1000, 4)])["first_negative_day"] is None

    def test_the_income_that_brings_it_back_is_named(self):
        walk = _walk(bills=[_bill(150000, 4)], incomes=[_income(200000, 20)])
        assert walk["rescue_event"] == (20, 200000, "pay")

    def test_income_that_does_not_clear_the_overdraft_is_not_a_rescue(self):
        walk = _walk(bills=[_bill(150000, 4)], incomes=[_income(1000, 20)])
        assert walk["rescue_event"] is None

    def test_only_the_first_rescue_is_reported(self):
        walk = _walk(
            bills=[_bill(150000, 4)],
            incomes=[_income(200000, 20), _income(200000, 25)],
        )
        assert walk["rescue_event"][0] == 20
