"""Tests for the CreditLimitChange value object."""

import pytest

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.credit_limit_change import CreditLimitChange
from clear_budget.shared.errors import InvalidCreditLimitChangeError


def _change(year=2026, month=6, day=15, pence=100000) -> CreditLimitChange:
    return CreditLimitChange(
        effective_year=year,
        effective_month=month,
        effective_day=day,
        new_limit=Amount(pence=pence),
    )


class TestCreditLimitChange:
    def test_valid_change_exposes_sort_key(self) -> None:
        change = _change()
        assert change.new_limit.pence == 100000
        assert change.sort_key == (2026, 6, 15)

    def test_rejects_month_below_one(self) -> None:
        with pytest.raises(InvalidCreditLimitChangeError):
            _change(month=0)

    def test_rejects_month_above_twelve(self) -> None:
        with pytest.raises(InvalidCreditLimitChangeError):
            _change(month=13)

    def test_rejects_day_zero(self) -> None:
        with pytest.raises(InvalidCreditLimitChangeError):
            _change(day=0)

    def test_rejects_day_beyond_month_length(self) -> None:
        with pytest.raises(InvalidCreditLimitChangeError):
            _change(year=2026, month=2, day=29)

    def test_accepts_leap_day(self) -> None:
        change = _change(year=2028, month=2, day=29)
        assert change.effective_day == 29
