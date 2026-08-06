"""Money, percentage and category formatting.

These moved out of the UI layer, which is excluded from the coverage gate
wholesale. Turning pence into a figure a person reads is not presentation: it
is where a budgeting application gets a number wrong in a way the user
believes, and until now it was the one part of `format_helpers` with nothing
holding it.
"""

import pytest

from clear_budget.application.formatting import fmt, format_category, percentage
from clear_budget.application.reporting.document import money
from clear_budget.shared.currency import DEFAULT_CURRENCY, set_currency


@pytest.fixture(autouse=True)
def _restore_currency():
    """The active currency is process-global; put it back after each test."""
    yield
    set_currency(DEFAULT_CURRENCY.code)


class TestMoneyOnScreen:
    def test_an_int_is_pence(self) -> None:
        assert fmt(100) == "£1.00"

    def test_a_float_is_already_pounds(self) -> None:
        assert fmt(100.0) == "£100.00"

    def test_the_int_float_overload_differs_by_a_factor_of_a_hundred(self) -> None:
        """Pinned deliberately.

        The same literal means two different sums depending on its type, with
        no error if a caller gets it wrong. Sixty-two call sites rely on this,
        so it is preserved; this test exists so changing it cannot be silent.
        """
        assert fmt(100) != fmt(100.0)

    def test_pence_below_a_unit_keep_two_decimals(self) -> None:
        assert fmt(5) == "£0.05"

    def test_the_active_currency_symbol_is_used(self) -> None:
        set_currency("USD")
        assert fmt(100) == "$1.00"

    def test_an_unknown_currency_code_falls_back_to_the_default(self) -> None:
        set_currency("XXX")
        assert fmt(100) == "£1.00"


class TestScreenAndReportDisagree:
    """The two formats this application ships, recorded rather than discovered.

    `reporting.document.money` groups thousands and puts the sign before the
    symbol. The on-screen `fmt` does neither. The report's form is the correct
    one; changing the screen to match is a visible change to every figure in
    the application and so is a decision, not a refactor.
    """

    def test_the_screen_omits_the_thousands_separator(self) -> None:
        assert money(123456) == "£1,234.56"
        assert fmt(123456) == "£1234.56"

    def test_a_negative_renders_the_symbol_and_sign_the_other_way_round(self) -> None:
        assert money(-123456) == "-£1,234.56"
        assert fmt(-123456) == "£-1234.56"

    def test_they_agree_on_a_small_positive_amount(self) -> None:
        assert money(5) == fmt(5)


class TestPercentage:
    def test_one_decimal_place(self) -> None:
        assert percentage(75.0) == "75.0%"

    def test_it_rounds_rather_than_truncates(self) -> None:
        assert percentage(66.666) == "66.7%"

    def test_zero_and_negative_are_formatted_the_same_way(self) -> None:
        assert percentage(0) == "0.0%"
        assert percentage(-12.34) == "-12.3%"


class TestCategoryLabels:
    def test_underscores_become_spaces_and_words_are_capitalised(self) -> None:
        assert format_category("credit_payment") == "Credit Payment"

    def test_a_plural_category_reads_as_a_single_item(self) -> None:
        assert format_category("subscriptions") == "Subscription"
        assert format_category("utilities") == "Utility"

    def test_an_unmapped_category_passes_through(self) -> None:
        assert format_category("housing") == "Housing"
