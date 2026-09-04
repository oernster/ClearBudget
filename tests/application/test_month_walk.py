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


class TestTheDeadline:
    """`first_breach_day` is the day any rescue has to beat.

    The Solvency forward blocks print an amount ("needs 268.13") and an amount
    with no deadline is not actionable: money that lands after the payment was
    refused did not keep the month afloat. This is the day it has to land by.
    """

    def test_it_is_the_first_day_the_balance_goes_under(self):
        assert _walk(bills=[_bill(150000, 4)])["first_breach_day"] == 4

    def test_a_month_that_never_goes_under_has_no_deadline(self):
        assert _walk(bills=[_bill(1000, 4)])["first_breach_day"] is None

    def test_it_is_the_first_breach_not_the_lowest_day(self):
        """A month can dip on one day and reach its worst on a later one.

        The money has to get in front of the FIRST refusal; clearing the low
        clears every day after it anyway.
        """
        walk = _walk(bills=[_bill(150000, 4), _bill(50000, 20)])
        assert walk["first_breach_day"] == 4
        assert walk["min_day"] == 20

    def test_a_month_that_opens_under_has_already_breached(self):
        """Reported as the start sentinel: the money is late before day one."""
        assert _walk(opening=-50000)["first_breach_day"] == LOW_AT_START


class TestTheFloor:
    """Borrowing the bank has agreed to is not a breach.

    The floor moves which day counts; it moves no balance, so every other
    figure the walk reports is untouched by it.
    """

    def test_a_dip_inside_an_arranged_facility_is_no_breach_at_all(self):
        walk = walk_month(
            _OPENING_PENCE, _summary([_bill(150000, 4)]), floor_pence=-100000
        )
        assert walk["first_breach_day"] is None
        assert walk["first_negative_day"] == 4

    def test_the_deadline_moves_out_to_the_day_the_facility_is_passed(self):
        walk = walk_month(
            _OPENING_PENCE,
            _summary([_bill(150000, 4), _bill(100000, 20)]),
            floor_pence=-100000,
        )
        assert walk["first_breach_day"] == 20

    def test_the_default_floor_makes_the_two_days_agree(self):
        walk = _walk(bills=[_bill(150000, 4)])
        assert walk["first_breach_day"] == walk["first_negative_day"]

    def test_the_floor_moves_no_balance(self):
        without = _walk(bills=[_bill(150000, 4)])
        with_floor = walk_month(
            _OPENING_PENCE, _summary([_bill(150000, 4)]), floor_pence=-100000
        )
        assert without["closing"] == with_floor["closing"]
        assert without["min_balance"] == with_floor["min_balance"]
        assert without["min_day"] == with_floor["min_day"]
