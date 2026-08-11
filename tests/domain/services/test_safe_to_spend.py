"""Tests for the Safe to Spend Today domain calculation."""

from datetime import date, timedelta

import pytest

from clear_budget.domain.services.safe_to_spend import (
    DayProjection,
    HorizonStrategy,
    SafeToSpendError,
    SafeToSpendResult,
    safe_to_spend,
)

_TODAY = date(2026, 8, 11)


def _projection(start: date, balances: list[int]) -> list[DayProjection]:
    """One DayProjection per balance, on consecutive days from start."""
    return [
        DayProjection(day=start + timedelta(days=i), balance_pence=pence)
        for i, pence in enumerate(balances)
    ]


def _flat_month_with_bill(
    *, opening: int, bill: int, bill_day_offset: int, length: int
) -> list[DayProjection]:
    """Level balance from today, dropping by `bill` at the given offset."""
    balances = [opening - (bill if i >= bill_day_offset else 0) for i in range(length)]
    return _projection(_TODAY, balances)


class TestFlatMonthOneBill:
    def test_value_is_balance_after_the_bill_on_its_due_day(self):
        projection = _flat_month_with_bill(
            opening=100000, bill=40000, bill_day_offset=9, length=20
        )
        result = safe_to_spend(projection=projection, today=_TODAY)
        assert result.amount_pence == 60000
        assert result.binding_day == _TODAY + timedelta(days=9)
        assert result.horizon_end == _TODAY + timedelta(days=19)
        assert result.floor_pence == 0

    def test_binding_day_is_first_day_at_the_minimum(self):
        # The bill day and every later day share the minimum; the bill day
        # is the constraint the user can act on, so it is the one named.
        projection = _flat_month_with_bill(
            opening=50000, bill=10000, bill_day_offset=5, length=15
        )
        result = safe_to_spend(projection=projection, today=_TODAY)
        assert result.binding_day == _TODAY + timedelta(days=5)


class TestBoundaryExactness:
    def test_spending_exactly_the_amount_leaves_min_at_the_floor(self):
        floor = 12500
        projection = _flat_month_with_bill(
            opening=87263, bill=31417, bill_day_offset=7, length=25
        )
        first = safe_to_spend(projection=projection, today=_TODAY, floor_pence=floor)
        respent = [
            DayProjection(day=d.day, balance_pence=d.balance_pence - first.amount_pence)
            for d in projection
        ]
        second = safe_to_spend(projection=respent, today=_TODAY, floor_pence=floor)
        min_balance = min(d.balance_pence for d in respent)
        assert min_balance == floor
        assert second.amount_pence == 0


class TestShortfall:
    def test_negative_result_equals_the_worst_dip_below_the_floor(self):
        projection = _flat_month_with_bill(
            opening=20000, bill=45000, bill_day_offset=3, length=10
        )
        result = safe_to_spend(projection=projection, today=_TODAY)
        assert result.amount_pence == -25000
        assert result.binding_day == _TODAY + timedelta(days=3)

    def test_shortfall_is_not_clamped_when_a_floor_is_set(self):
        projection = _projection(_TODAY, [5000, 5000, 5000])
        result = safe_to_spend(projection=projection, today=_TODAY, floor_pence=8000)
        assert result.amount_pence == -3000


class TestFloor:
    def test_floor_reduces_the_result_by_exactly_the_floor(self):
        projection = _flat_month_with_bill(
            opening=90000, bill=30000, bill_day_offset=12, length=28
        )
        without = safe_to_spend(projection=projection, today=_TODAY, floor_pence=0)
        with_floor = safe_to_spend(
            projection=projection, today=_TODAY, floor_pence=10000
        )
        assert without.amount_pence - with_floor.amount_pence == 10000
        assert with_floor.floor_pence == 10000


class TestHorizon:
    def _income_then_big_bill(self) -> tuple[list[DayProjection], list[date]]:
        """Income on day 10 (offset), a huge bill after it."""
        income_day = _TODAY + timedelta(days=10)
        balances = [30000] * 10  # before income
        balances += [130000] * 5  # income landed
        balances += [10000] * 10  # big bill after the income event
        return _projection(_TODAY, balances), [income_day]

    def test_until_next_income_ignores_a_bill_after_the_income(self):
        projection, income_days = self._income_then_big_bill()
        result = safe_to_spend(
            projection=projection, today=_TODAY, income_days=income_days
        )
        assert result.amount_pence == 30000
        assert result.horizon_end == _TODAY + timedelta(days=9)

    def test_full_forecast_sees_the_bill_after_the_income(self):
        projection, income_days = self._income_then_big_bill()
        result = safe_to_spend(
            projection=projection,
            today=_TODAY,
            income_days=income_days,
            horizon=HorizonStrategy.FULL_FORECAST,
        )
        assert result.amount_pence == 10000
        assert result.horizon_end == _TODAY + timedelta(days=24)

    def test_income_today_does_not_end_the_horizon(self):
        # Income dated today is inside P(today); the horizon runs to the day
        # before the NEXT income event, not today.
        projection = _projection(_TODAY, [80000, 60000, 60000, 90000])
        result = safe_to_spend(
            projection=projection,
            today=_TODAY,
            income_days=[_TODAY, _TODAY + timedelta(days=3)],
        )
        assert result.horizon_end == _TODAY + timedelta(days=2)
        assert result.amount_pence == 60000

    def test_no_future_income_degrades_to_the_full_window(self):
        projection = _projection(_TODAY, [40000, 35000, 30000])
        result = safe_to_spend(projection=projection, today=_TODAY, income_days=[])
        assert result.horizon_end == _TODAY + timedelta(days=2)
        assert result.amount_pence == 30000

    def test_income_past_the_projection_never_extends_the_horizon(self):
        projection = _projection(_TODAY, [40000, 30000])
        result = safe_to_spend(
            projection=projection,
            today=_TODAY,
            income_days=[_TODAY + timedelta(days=90)],
        )
        assert result.horizon_end == _TODAY + timedelta(days=1)


class TestDeterminism:
    def test_identical_inputs_give_identical_results(self):
        projection = _flat_month_with_bill(
            opening=77777, bill=22222, bill_day_offset=4, length=18
        )
        income_days = [_TODAY + timedelta(days=6)]
        first = safe_to_spend(
            projection=projection, today=_TODAY, income_days=income_days
        )
        second = safe_to_spend(
            projection=projection, today=_TODAY, income_days=income_days
        )
        assert first == second
        assert isinstance(first, SafeToSpendResult)

    def test_days_before_today_are_ignored(self):
        # A projection covering the whole month: the pre-today stretch holds
        # a deep dip that already happened and must not bind the result.
        past = _projection(_TODAY - timedelta(days=5), [-90000] * 5)
        future = _projection(_TODAY, [25000, 20000, 30000])
        result = safe_to_spend(projection=past + future, today=_TODAY)
        assert result.amount_pence == 20000
        assert result.binding_day == _TODAY + timedelta(days=1)


class TestMonotonicity:
    def _base(self) -> list[DayProjection]:
        return _flat_month_with_bill(
            opening=60000, bill=15000, bill_day_offset=8, length=20
        )

    def test_an_extra_bill_in_horizon_never_increases_the_result(self):
        base = self._base()
        extra_bill = [
            DayProjection(
                day=d.day,
                balance_pence=d.balance_pence
                - (5000 if d.day >= _TODAY + timedelta(days=12) else 0),
            )
            for d in base
        ]
        before = safe_to_spend(projection=base, today=_TODAY)
        after = safe_to_spend(projection=extra_bill, today=_TODAY)
        assert after.amount_pence <= before.amount_pence

    def test_extra_income_in_horizon_never_decreases_the_result(self):
        base = self._base()
        extra_income = [
            DayProjection(
                day=d.day,
                balance_pence=d.balance_pence
                + (5000 if d.day >= _TODAY + timedelta(days=2) else 0),
            )
            for d in base
        ]
        before = safe_to_spend(projection=base, today=_TODAY)
        after = safe_to_spend(projection=extra_income, today=_TODAY)
        assert after.amount_pence >= before.amount_pence


class TestCurrencyPrecision:
    def test_odd_pence_survive_exactly(self):
        projection = _projection(_TODAY, [10001, 9999, 10003])
        result = safe_to_spend(projection=projection, today=_TODAY, floor_pence=33)
        assert result.amount_pence == 9999 - 33


class TestInputValidation:
    def test_negative_floor_is_rejected(self):
        projection = _projection(_TODAY, [1000])
        with pytest.raises(SafeToSpendError):
            safe_to_spend(projection=projection, today=_TODAY, floor_pence=-1)

    def test_empty_projection_is_rejected(self):
        with pytest.raises(SafeToSpendError):
            safe_to_spend(projection=[], today=_TODAY)

    def test_projection_starting_after_today_is_rejected(self):
        projection = _projection(_TODAY + timedelta(days=1), [1000, 2000])
        with pytest.raises(SafeToSpendError):
            safe_to_spend(projection=projection, today=_TODAY)
