"""Reading a typed amount back, the inverse of how money is rendered.

This exists because the two had drifted apart. `_render` groups thousands, so
the application printed "1,400.00" and then refused to read it: a plain
`float()` raised, the entry was treated as invalid and a rent increase entered
as "1,400" was never recorded. Anything this module can print, it must be able
to read.
"""

import pytest

from clear_budget.application.formatting import money_from_pounds, pounds_from_text


class TestWhatTheApplicationItselfPrints:
    @pytest.mark.parametrize("pounds", [0.0, 1.5, 95.0, 1350.0, 1400.0, 123456.78])
    def test_every_rendered_figure_reads_back(self, pounds: float) -> None:
        assert pounds_from_text(money_from_pounds(pounds)) == pytest.approx(pounds)

    def test_a_negative_reads_back_with_its_sign(self) -> None:
        """`_render` leads with the sign, so the reader has to strip it first."""
        assert pounds_from_text(money_from_pounds(-1400.0)) == pytest.approx(-1400.0)


class TestWhatAPersonTypes:
    @pytest.mark.parametrize(
        ("typed", "expected"),
        [
            ("1400", 1400.0),
            ("1400.00", 1400.0),
            ("1,400", 1400.0),
            ("1,400.50", 1400.5),
            ("£1400", 1400.0),
            ("£1,400.00", 1400.0),
            ("  1400  ", 1400.0),
            ("1 400", 1400.0),
            ("-£1,400.00", -1400.0),
        ],
    )
    def test_ordinary_entries_are_read(self, typed: str, expected: float) -> None:
        assert pounds_from_text(typed) == pytest.approx(expected)


class TestWhatCannotBeRead:
    @pytest.mark.parametrize(
        "typed", ["", "   ", "abc", "1.2.3", "one hundred", "£", "-", ","]
    )
    def test_it_answers_None_rather_than_raising(self, typed: str) -> None:
        assert pounds_from_text(typed) is None


class TestAMultiCharacterSymbol:
    def test_the_symbol_is_removed_by_length_not_as_a_character_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`lstrip("A$")` would eat a leading A or $ anywhere; slicing does not."""
        monkeypatch.setattr(
            "clear_budget.application.formatting.get_symbol", lambda: "A$"
        )
        assert pounds_from_text("A$1400") == pytest.approx(1400.0)
        assert pounds_from_text("1400") == pytest.approx(1400.0)
