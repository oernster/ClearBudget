"""The two statements under the spendable headline, told apart and why.

The reach sentence is a caution about a figure the reader can still act on.
The shortfall sentence reports a gap no restraint closes, so it is rendered in
the traffic light's red rather than the muted body colour. A QLabel carries one
colour, so telling them apart in the text is what lets them differ on screen.

Qt-free: the builder is a plain function over a plain result (see this
package's docstring).
"""

from datetime import date
from types import SimpleNamespace

from clear_budget.ui.views._solvency_panel_safe_to_spend import (
    SolvencyPanelSafeToSpendMixin,
)


class _Lines(SolvencyPanelSafeToSpendMixin):
    """The mixin alone, which is all the builder needs."""


def _result(
    *,
    shortfall_pence: int = 0,
    shortfall_day=None,
    floor_pence: int = 2000,
    reserved_pence: int = 0,
):
    return SimpleNamespace(
        covered_end=date(2026, 10, 31),
        binding_day=date(2026, 10, 14),
        floor_pence=floor_pence,
        reserved_pence=reserved_pence,
        shortfall_pence=shortfall_pence,
        shortfall_day=shortfall_day,
        has_shortfall=shortfall_day is not None,
    )


class TestTheReachSentence:
    def test_it_names_the_month_the_promise_reaches_and_the_day_that_limits_it(self):
        reach, _ = _Lines()._sts_detail_lines(_result())
        assert "Holds every day through October 2026" in reach
        assert "constrained by 14 Oct" in reach

    def test_a_buffer_is_named_so_the_promise_can_be_checked(self):
        reach, _ = _Lines()._sts_detail_lines(_result(floor_pence=2000))
        assert "above your £20.00 buffer" in reach

    def test_a_reserve_is_named_apart_from_the_buffer(self):
        """It is not buffer, so calling it buffer would be a plain untruth."""
        reach, _ = _Lines()._sts_detail_lines(
            _result(floor_pence=36167, reserved_pence=21167)
        )
        assert "above your £150.00 buffer and £211.67 set aside" in reach

    def test_a_reserve_with_no_buffer_stands_on_its_own(self):
        reach, _ = _Lines()._sts_detail_lines(
            _result(floor_pence=21167, reserved_pence=21167)
        )
        assert "above £211.67 set aside" in reach
        assert "buffer" not in reach

    def test_a_zero_buffer_says_zero_rather_than_naming_an_amount(self):
        reach, _ = _Lines()._sts_detail_lines(_result(floor_pence=0))
        assert "above zero" in reach
        assert "buffer" not in reach


class TestTheShortfallSentence:
    def test_a_month_with_no_shortfall_produces_nothing_to_render(self):
        # An empty string is what hides the red label, so a healthy budget
        # never shows a blank line where an alarm would be.
        reach, shortfall = _Lines()._sts_detail_lines(_result())
        assert shortfall == ""
        assert reach

    def test_a_shortfall_is_returned_apart_from_the_reach_sentence(self):
        # The separation IS the feature: one label cannot hold two colours.
        reach, shortfall = _Lines()._sts_detail_lines(
            _result(shortfall_pence=28475, shortfall_day=date(2026, 11, 14))
        )
        assert "short whatever you do" not in reach
        assert "November 2026 is £284.75 short whatever you do" in shortfall
        assert "spending this deepens it" in shortfall

    def test_the_shortfall_sentence_stands_alone_without_the_reach_wording(self):
        _, shortfall = _Lines()._sts_detail_lines(
            _result(shortfall_pence=28475, shortfall_day=date(2026, 11, 14))
        )
        assert "Holds every day" not in shortfall
