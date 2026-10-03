"""Reading a typed amount into whole pence, never through a float.

Typed amounts used to go through `float()` and `round(x * 100)`, so the figure
stored was not always the figure typed: 0.125 became 12p, 0.135 became 14p and
2.675 became 268p, contrary to "nothing rounds away". `nan`, `inf` and negative
entries raised errors the dialogs did not catch; 10**19 pence overflowed SQLite.

The rule now: the amount is read as an exact decimal and converted to integer
pence. An entry finer than a penny is REFUSED rather than rounded, because any
rounding rule silently stores a figure the user did not type. So are anything
that is not a finite number, a negative amount and anything above
MAX_AMOUNT_PENCE. Each refusal carries a message fit to show the user.

It is also the inverse of how money is rendered: anything the application
prints, it must be able to read back (the reason it accepts "1,400.00").
"""

import sqlite3

import pytest

from clear_budget.application.formatting import money_from_pence, pence_from_text
from clear_budget.domain.value_objects.amount import MAX_AMOUNT_PENCE
from clear_budget.shared.errors import InvalidAmountError

_SQLITE_INTEGER_MAX = 2**63 - 1
_FLOAT_EXACT_INTEGER_MAX = 2**53


class TestWhatTheApplicationItselfPrints:
    @pytest.mark.parametrize("pence", [0, 150, 9500, 135000, 140000, 12345678])
    def test_every_rendered_figure_reads_back(self, pence: int) -> None:
        assert pence_from_text(money_from_pence(pence)) == pence

    def test_the_largest_allowed_figure_reads_back(self) -> None:
        assert pence_from_text(money_from_pence(MAX_AMOUNT_PENCE)) == MAX_AMOUNT_PENCE


class TestWhatAPersonTypes:
    @pytest.mark.parametrize(
        ("typed", "pence"),
        [
            ("1400", 140000),
            ("1400.00", 140000),
            ("1,400", 140000),
            ("1,400.50", 140050),
            ("£1400", 140000),
            ("£1,500", 150000),
            ("  1400  ", 140000),
            ("1 400", 140000),
            ("0.01", 1),
            ("2.675000", None),
            ("1.50000", 150),
            ("1e2", 10000),
            ("-0", 0),
        ],
    )
    def test_ordinary_entries_are_read_exactly(self, typed: str, pence) -> None:
        if pence is None:
            with pytest.raises(InvalidAmountError):
                pence_from_text(typed)
        else:
            assert pence_from_text(typed) == pence


class TestNothingRoundsAway:
    @pytest.mark.parametrize(
        "typed", ["0.125", "0.135", "2.675", "1.005", "19.999", "0.001", "1e-999999"]
    )
    def test_a_fraction_of_a_penny_is_refused_not_rounded(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError) as caught:
            pence_from_text(typed)
        assert "penny" in str(caught.value)

    def test_trailing_zeros_past_the_penny_are_not_a_fraction(self) -> None:
        assert pence_from_text("2.6700") == 267


class TestWhatIsRefused:
    @pytest.mark.parametrize(
        "typed", ["abc", "1.2.3", "one hundred", "£", "-", ",", "nan", "NaN", "inf"]
    )
    def test_not_a_number(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError) as caught:
            pence_from_text(typed)
        assert "not an amount" in str(caught.value)

    @pytest.mark.parametrize("typed", ["-Infinity", "sNaN"])
    def test_other_non_finite_spellings(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError):
            pence_from_text(typed)

    @pytest.mark.parametrize("typed", ["", "   "])
    def test_nothing_typed(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError) as caught:
            pence_from_text(typed)
        assert "Enter an amount" in str(caught.value)

    @pytest.mark.parametrize("typed", ["-5", "-£1,400.00", "£-5"])
    def test_a_negative_amount(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError) as caught:
            pence_from_text(typed)
        assert "negative" in str(caught.value)

    @pytest.mark.parametrize(
        "typed", ["1000000000.01", "100000000000000000", "1e999999999"]
    )
    def test_more_than_the_cap(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError) as caught:
            pence_from_text(typed)
        assert money_from_pence(MAX_AMOUNT_PENCE) in str(caught.value)


class TestASignedField:
    """Only the bank balance is signed: an overdrawn account is negative."""

    @pytest.mark.parametrize(
        ("typed", "pence"),
        [("-5", -500), ("-£1,250.50", -125050), ("£-5", -500), ("12", 1200)],
    )
    def test_a_sign_is_read(self, typed: str, pence: int) -> None:
        assert pence_from_text(typed, signed=True) == pence

    def test_a_rendered_overdraft_reads_back(self) -> None:
        assert pence_from_text(money_from_pence(-125050), signed=True) == -125050

    @pytest.mark.parametrize("typed", ["--5", "-£-5"])
    def test_a_doubled_minus_is_not_an_amount(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError) as caught:
            pence_from_text(typed, signed=True)
        assert "not an amount" in str(caught.value)

    @pytest.mark.parametrize("typed", ["-0.125", "-1000000000.01", "-inf", ""])
    def test_the_other_rules_still_hold(self, typed: str) -> None:
        with pytest.raises(InvalidAmountError):
            pence_from_text(typed, signed=True)


class TestTheCap:
    def test_it_leaves_room_for_sums_far_below_sqlite_integer(self) -> None:
        """Totals add amounts; SQLite's SUM raises on overflow (measured)."""
        assert MAX_AMOUNT_PENCE * 10**7 < _SQLITE_INTEGER_MAX

    def test_it_renders_to_the_penny_through_a_float(self) -> None:
        """`fmt` divides pence by 100 as a float; exact below 2**53."""
        assert MAX_AMOUNT_PENCE < _FLOAT_EXACT_INTEGER_MAX

    def test_the_cap_itself_can_be_stored(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t (amount_pence INTEGER NOT NULL)")
        conn.execute("INSERT INTO t VALUES (?)", (pence_from_text("1000000000"),))
        assert conn.execute("SELECT amount_pence FROM t").fetchone()[0] == (
            MAX_AMOUNT_PENCE
        )


class TestAMultiCharacterSymbol:
    def test_the_symbol_is_removed_by_length_not_as_a_character_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`lstrip("A$")` would eat a leading A or $ anywhere; slicing does not."""
        monkeypatch.setattr(
            "clear_budget.application.formatting.get_symbol", lambda: "A$"
        )
        assert pence_from_text("A$1400") == 140000
        assert pence_from_text("1400") == 140000
