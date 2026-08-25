"""How often a commitment comes round again.

`annual` and a twelve-month interval are the same interval said two ways, so
the maths only ever reads `months` and the label normalises on the way out.
"""

import pytest

from clear_budget.domain.value_objects.recurrence import MONTHS_IN_YEAR, Recurrence
from clear_budget.shared.errors import InvalidCommitmentError


class TestConstruction:
    def test_once_has_no_interval(self):
        assert Recurrence.once().months is None
        assert Recurrence.once().is_once

    def test_annual_is_twelve_months(self):
        assert Recurrence.annual().months == MONTHS_IN_YEAR
        assert not Recurrence.annual().is_once

    def test_every_months_keeps_its_interval(self):
        assert Recurrence.every_months(3).months == 3

    @pytest.mark.parametrize("months", [0, -1])
    def test_an_interval_shorter_than_a_month_is_refused(self, months):
        with pytest.raises(InvalidCommitmentError):
            Recurrence.every_months(months)


class TestParsing:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("once", None),
            ("annual", MONTHS_IN_YEAR),
            ("months:3", 3),
            ("months:12", MONTHS_IN_YEAR),
        ],
    )
    def test_every_stored_label_reads_back(self, text, expected):
        assert Recurrence.parse(text).months == expected

    @pytest.mark.parametrize("text", ["", "yearly", "months:", "months:x", "months:-1"])
    def test_an_unrecognised_label_is_refused(self, text):
        with pytest.raises(InvalidCommitmentError):
            Recurrence.parse(text)


class TestRoundTrip:
    @pytest.mark.parametrize("text", ["once", "annual", "months:3"])
    def test_a_label_survives_a_round_trip(self, text):
        assert str(Recurrence.parse(text)) == text

    def test_a_twelve_month_interval_normalises_to_annual(self):
        """The same interval said the way a person says it."""
        assert str(Recurrence.parse("months:12")) == "annual"
