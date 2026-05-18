"""Tests for YearMonth value object."""

from datetime import datetime

import pytest

from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.shared.errors import InvalidYearMonthError


class TestYearMonthCreation:
    """Test YearMonth creation and validation."""

    def test_create_valid(self) -> None:
        """Test creating valid YearMonth."""
        ym = YearMonth(year=2026, month=5)
        assert ym.year == 2026
        assert ym.month == 5

    def test_invalid_month_low(self) -> None:
        """Test month < 1 raises error."""
        with pytest.raises(InvalidYearMonthError):
            YearMonth(year=2026, month=0)

    def test_invalid_month_high(self) -> None:
        """Test month > 12 raises error."""
        with pytest.raises(InvalidYearMonthError):
            YearMonth(year=2026, month=13)

    def test_invalid_year_too_low(self) -> None:
        """Test year < 1900 raises error."""
        with pytest.raises(InvalidYearMonthError):
            YearMonth(year=1899, month=1)

    def test_invalid_year_too_high(self) -> None:
        """Test year > 2100 raises error."""
        with pytest.raises(InvalidYearMonthError):
            YearMonth(year=2101, month=1)

    def test_parse_valid(self) -> None:
        """Test parsing YYYY-MM string."""
        ym = YearMonth.parse("2026-05")
        assert ym.year == 2026
        assert ym.month == 5

    def test_parse_invalid_format(self) -> None:
        """Test parsing invalid format raises error."""
        with pytest.raises(InvalidYearMonthError):
            YearMonth.parse("2026/05")

    def test_parse_strips_whitespace(self) -> None:
        """Test that parse strips whitespace."""
        ym = YearMonth.parse("  2026-05  ")
        assert str(ym) == "2026-05"


class TestYearMonthFormatting:
    """Test YearMonth string formatting."""

    def test_str_format(self) -> None:
        """Test __str__ produces YYYY-MM format."""
        ym = YearMonth(year=2026, month=5)
        assert str(ym) == "2026-05"

    def test_str_zero_padded(self) -> None:
        """Test month is zero-padded."""
        ym = YearMonth(year=2026, month=1)
        assert str(ym) == "2026-01"

    def test_repr(self) -> None:
        """Test __repr__."""
        ym = YearMonth(year=2026, month=5)
        assert repr(ym) == "YearMonth(2026-05)"


class TestYearMonthArithmetic:
    """Test YearMonth arithmetic operations."""

    def test_next_month(self) -> None:
        """Test next_month() within same year."""
        ym = YearMonth(year=2026, month=5)
        next_ym = ym.next_month()
        assert next_ym.year == 2026
        assert next_ym.month == 6

    def test_next_month_year_wrap(self) -> None:
        """Test next_month() wraps to next year."""
        ym = YearMonth(year=2026, month=12)
        next_ym = ym.next_month()
        assert next_ym.year == 2027
        assert next_ym.month == 1

    def test_previous_month(self) -> None:
        """Test previous_month() within same year."""
        ym = YearMonth(year=2026, month=6)
        prev_ym = ym.previous_month()
        assert prev_ym.year == 2026
        assert prev_ym.month == 5

    def test_previous_month_year_wrap(self) -> None:
        """Test previous_month() wraps to previous year."""
        ym = YearMonth(year=2026, month=1)
        prev_ym = ym.previous_month()
        assert prev_ym.year == 2025
        assert prev_ym.month == 12

    def test_add_months_positive(self) -> None:
        """Test add_months() with positive count."""
        ym = YearMonth(year=2026, month=11)
        result = ym.add_months(3)
        assert result.year == 2027
        assert result.month == 2

    def test_add_months_negative(self) -> None:
        """Test add_months() with negative count."""
        ym = YearMonth(year=2026, month=3)
        result = ym.add_months(-4)
        assert result.year == 2025
        assert result.month == 11


class TestYearMonthComparison:
    """Test YearMonth comparison operations."""

    def test_less_than(self) -> None:
        """Test < operator."""
        a = YearMonth(year=2026, month=5)
        b = YearMonth(year=2026, month=6)
        assert a < b

    def test_less_than_different_year(self) -> None:
        """Test < operator across years."""
        a = YearMonth(year=2025, month=12)
        b = YearMonth(year=2026, month=1)
        assert a < b

    def test_less_than_equal(self) -> None:
        """Test <= operator."""
        a = YearMonth(year=2026, month=5)
        b = YearMonth(year=2026, month=6)
        c = YearMonth(year=2026, month=5)
        assert a <= b
        assert a <= c
        assert not (b <= a)

    def test_greater_than(self) -> None:
        """Test > operator."""
        a = YearMonth(year=2026, month=6)
        b = YearMonth(year=2026, month=5)
        assert a > b
        assert not (b > a)

    def test_greater_than_equal(self) -> None:
        """Test >= operator."""
        a = YearMonth(year=2026, month=6)
        b = YearMonth(year=2026, month=5)
        c = YearMonth(year=2026, month=6)
        assert a >= b
        assert a >= c
        assert not (b >= a)

    def test_equal(self) -> None:
        """Test == operator."""
        a = YearMonth(year=2026, month=5)
        b = YearMonth(year=2026, month=5)
        assert a == b

    def test_not_equal(self) -> None:
        """Test != operator."""
        a = YearMonth(year=2026, month=5)
        b = YearMonth(year=2026, month=6)
        assert a != b

    def test_equality_with_non_yearmonth_type(self) -> None:
        """Test equality with non-YearMonth returns False."""
        ym = YearMonth(year=2026, month=5)
        assert ym != "2026-05"
        assert ym != (2026, 5)

    def test_comparison_with_non_yearmonth_type_error(self) -> None:
        """Test comparison with non-YearMonth raises TypeError."""
        ym = YearMonth(year=2026, month=5)
        with pytest.raises(TypeError):
            ym < "2026-06"  # type: ignore
        with pytest.raises(TypeError):
            ym <= "2026-06"  # type: ignore
        with pytest.raises(TypeError):
            ym > "2026-06"  # type: ignore
        with pytest.raises(TypeError):
            ym >= "2026-06"  # type: ignore

    def test_hash(self) -> None:
        """Test that equal YearMonths have equal hashes."""
        a = YearMonth(year=2026, month=5)
        b = YearMonth(year=2026, month=5)
        assert hash(a) == hash(b)

    def test_can_use_in_set(self) -> None:
        """Test that YearMonth can be used in sets."""
        a = YearMonth(year=2026, month=5)
        b = YearMonth(year=2026, month=5)
        s = {a, b}
        assert len(s) == 1


class TestYearMonthToday:
    """Test YearMonth.today() method."""

    def test_today_returns_current_month(self) -> None:
        """Test today() returns current year and month."""
        now = datetime.now()
        ym = YearMonth.today()
        assert ym.year == now.year
        assert ym.month == now.month
