"""Tests for Amount value object."""

import pytest

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.shared.errors import InvalidAmountError


class TestAmountCreation:
    """Test Amount creation and validation."""

    def test_create_from_pence(self) -> None:
        """Test creating Amount directly from pence."""
        amt = Amount(pence=500)
        assert amt.pence == 500
        assert amt.pounds == 5.0

    def test_create_from_pounds(self) -> None:
        """Test creating Amount from pounds."""
        amt = Amount.from_pounds(10.50)
        assert amt.pence == 1050
        assert amt.pounds == 10.50

    def test_create_zero(self) -> None:
        """Test creating zero amount."""
        amt = Amount.zero()
        assert amt.pence == 0
        assert amt.pounds == 0.0

    def test_negative_amount_raises_error(self) -> None:
        """Test that negative amounts raise InvalidAmountError."""
        with pytest.raises(InvalidAmountError):
            Amount(pence=-100)

    def test_rounding_from_pounds(self) -> None:
        """Test that fractional pence are rounded."""
        amt = Amount.from_pounds(1.234)
        assert amt.pence == 123  # rounds to nearest pence


class TestAmountFormatting:
    """Test Amount string formatting."""

    def test_str_format(self) -> None:
        """Test __str__ produces £X.XX format."""
        amt = Amount(pence=1234)
        assert str(amt) == "£12.34"

    def test_str_zero(self) -> None:
        """Test zero amount formatting."""
        assert str(Amount.zero()) == "£0.00"

    def test_repr(self) -> None:
        """Test __repr__."""
        amt = Amount(pence=500)
        assert "5.0" in repr(amt)


class TestAmountArithmetic:
    """Test Amount arithmetic operations."""

    def test_add(self) -> None:
        """Test adding two amounts."""
        a = Amount(pence=500)
        b = Amount(pence=300)
        result = a + b
        assert result.pence == 800

    def test_add_type_error(self) -> None:
        """Test adding non-Amount raises TypeError."""
        amt = Amount(pence=100)
        with pytest.raises(TypeError):
            amt + 50  # type: ignore

    def test_multiply_by_scalar(self) -> None:
        """Test multiplying amount by scalar."""
        amt = Amount(pence=100)
        result = amt * 2.5
        assert result.pence == 250

    def test_multiply_reverse(self) -> None:
        """Test scalar * amount."""
        amt = Amount(pence=100)
        result = 3 * amt
        assert result.pence == 300


class TestAmountComparison:
    """Test Amount comparison operations."""

    def test_less_than(self) -> None:
        """Test < operator."""
        a = Amount(pence=100)
        b = Amount(pence=200)
        assert a < b
        assert not (b < a)

    def test_less_than_equal(self) -> None:
        """Test <= operator."""
        a = Amount(pence=100)
        b = Amount(pence=200)
        c = Amount(pence=100)
        assert a <= b
        assert a <= c
        assert not (b <= a)

    def test_greater_than(self) -> None:
        """Test > operator."""
        a = Amount(pence=200)
        b = Amount(pence=100)
        assert a > b
        assert not (b > a)

    def test_greater_than_equal(self) -> None:
        """Test >= operator."""
        a = Amount(pence=200)
        b = Amount(pence=100)
        c = Amount(pence=200)
        assert a >= b
        assert a >= c
        assert not (b >= a)

    def test_equal(self) -> None:
        """Test == operator."""
        a = Amount(pence=100)
        b = Amount(pence=100)
        c = Amount(pence=200)
        assert a == b
        assert not (a == c)

    def test_not_equal(self) -> None:
        """Test != operator."""
        a = Amount(pence=100)
        b = Amount(pence=200)
        assert a != b

    def test_comparison_with_non_amount_type_error(self) -> None:
        """Test comparison with non-Amount raises TypeError."""
        amt = Amount(pence=100)
        with pytest.raises(TypeError):
            amt < 100  # type: ignore
        with pytest.raises(TypeError):
            amt <= 100  # type: ignore
        with pytest.raises(TypeError):
            amt > 100  # type: ignore
        with pytest.raises(TypeError):
            amt >= 100  # type: ignore

    def test_multiply_by_non_numeric_type_error(self) -> None:
        """Test multiply with non-numeric type raises TypeError."""
        amt = Amount(pence=100)
        with pytest.raises(TypeError):
            amt * "5"  # type: ignore

    def test_hash(self) -> None:
        """Test that equal amounts have equal hashes."""
        a = Amount(pence=100)
        b = Amount(pence=100)
        assert hash(a) == hash(b)

    def test_can_use_in_set(self) -> None:
        """Test that Amount can be used in sets."""
        a = Amount(pence=100)
        b = Amount(pence=100)
        s = {a, b}
        assert len(s) == 1

    def test_equality_with_non_amount_type(self) -> None:
        """Test equality with non-Amount returns False."""
        amt = Amount(pence=100)
        assert amt != 100
        assert amt != "100"
