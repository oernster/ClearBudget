"""Tests for the effective credit limit derivation over scheduled changes."""

from datetime import date

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.services.credit_limit_schedule import (
    effective_credit_limit_pence,
    month_end_effective_limit_pence,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.credit_limit_change import CreditLimitChange


def _change(year: int, month: int, day: int, pence: int) -> CreditLimitChange:
    return CreditLimitChange(
        effective_year=year,
        effective_month=month,
        effective_day=day,
        new_limit=Amount(pence=pence),
    )


def _card(limit_pence: int = 50000, changes=()) -> CreditCard:
    return CreditCard(
        id=1,
        name="Card",
        credit_limit=Amount(pence=limit_pence),
        current_balance_used=Amount(pence=0),
        scheduled_limit_changes=tuple(changes),
    )


class TestEffectiveCreditLimit:
    def test_no_changes_returns_base_limit(self) -> None:
        card = _card(limit_pence=50000)
        assert effective_credit_limit_pence(card=card, as_of=date(2026, 6, 1)) == 50000

    def test_before_first_change_returns_base(self) -> None:
        card = _card(50000, [_change(2026, 6, 15, 100000)])
        assert effective_credit_limit_pence(card=card, as_of=date(2026, 6, 14)) == 50000

    def test_on_change_day_returns_new_limit(self) -> None:
        card = _card(50000, [_change(2026, 6, 15, 100000)])
        assert (
            effective_credit_limit_pence(card=card, as_of=date(2026, 6, 15)) == 100000
        )

    def test_walks_to_latest_applicable(self) -> None:
        card = _card(
            50000,
            [_change(2026, 6, 15, 100000), _change(2026, 7, 4, 120000)],
        )
        assert (
            effective_credit_limit_pence(card=card, as_of=date(2026, 7, 10)) == 120000
        )
        assert (
            effective_credit_limit_pence(card=card, as_of=date(2026, 6, 20)) == 100000
        )

    def test_two_changes_in_one_month_take_the_later_at_month_end(self) -> None:
        card = _card(
            50000,
            [_change(2026, 6, 10, 100000), _change(2026, 6, 20, 120000)],
        )
        assert month_end_effective_limit_pence(card=card, year=2026, month=6) == 120000
        assert (
            effective_credit_limit_pence(card=card, as_of=date(2026, 6, 15)) == 100000
        )

    def test_same_day_ties_resolve_to_last_entered(self) -> None:
        card = _card(
            50000,
            [_change(2026, 6, 10, 100000), _change(2026, 6, 10, 110000)],
        )
        assert (
            effective_credit_limit_pence(card=card, as_of=date(2026, 6, 10)) == 110000
        )

    def test_month_end_before_any_change_uses_base(self) -> None:
        card = _card(50000, [_change(2026, 8, 1, 100000)])
        assert month_end_effective_limit_pence(card=card, year=2026, month=6) == 50000

    def test_unsorted_input_still_resolves(self) -> None:
        card = _card(
            50000,
            [_change(2026, 7, 4, 120000), _change(2026, 6, 15, 100000)],
        )
        assert (
            effective_credit_limit_pence(card=card, as_of=date(2026, 7, 10)) == 120000
        )
