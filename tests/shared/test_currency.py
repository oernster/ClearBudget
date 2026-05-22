"""Tests for shared.currency module."""

import pytest

import clear_budget.shared.currency as currency_module
from clear_budget.shared.currency import (
    CURRENCIES,
    DEFAULT_CURRENCY,
    Currency,
    get_currency,
    get_symbol,
    set_currency,
)


@pytest.fixture(autouse=True)
def reset_currency():
    """Reset active currency to GBP after every test."""
    yield
    currency_module._active = DEFAULT_CURRENCY


class TestCurrencyDataclass:
    def test_currency_fields(self) -> None:
        c = Currency(code="GBP", symbol="£", name="British Pound")
        assert c.code == "GBP"
        assert c.symbol == "£"
        assert c.name == "British Pound"

    def test_currency_is_frozen(self) -> None:
        c = Currency(code="GBP", symbol="£", name="British Pound")
        with pytest.raises(Exception):
            c.code = "USD"  # type: ignore[misc]


class TestCurrenciesList:
    def test_currencies_not_empty(self) -> None:
        assert len(CURRENCIES) > 0

    def test_gbp_is_first(self) -> None:
        assert CURRENCIES[0].code == "GBP"

    def test_all_have_non_empty_fields(self) -> None:
        for c in CURRENCIES:
            assert c.code
            assert c.symbol
            assert c.name

    def test_codes_are_unique(self) -> None:
        codes = [c.code for c in CURRENCIES]
        assert len(codes) == len(set(codes))


class TestDefaultCurrency:
    def test_default_is_gbp(self) -> None:
        assert DEFAULT_CURRENCY.code == "GBP"
        assert DEFAULT_CURRENCY.symbol == "£"


class TestGetCurrency:
    def test_returns_active_currency(self) -> None:
        assert get_currency() is currency_module._active

    def test_returns_currency_object(self) -> None:
        result = get_currency()
        assert isinstance(result, Currency)


class TestGetSymbol:
    def test_default_symbol_is_gbp(self) -> None:
        assert get_symbol() == "£"

    def test_symbol_changes_after_set(self) -> None:
        set_currency("USD")
        assert get_symbol() == "$"


class TestSetCurrency:
    def test_set_known_code(self) -> None:
        set_currency("USD")
        assert get_currency().code == "USD"
        assert get_symbol() == "$"

    def test_set_unknown_code_falls_back_to_gbp(self) -> None:
        set_currency("XYZ")
        assert get_currency().code == "GBP"

    def test_set_gbp_explicitly(self) -> None:
        set_currency("USD")
        set_currency("GBP")
        assert get_symbol() == "£"

    def test_set_each_currency_in_list(self) -> None:
        for c in CURRENCIES:
            set_currency(c.code)
            assert get_symbol() == c.symbol
