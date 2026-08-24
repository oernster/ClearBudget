"""Qt-free tests for the ring-order helpers behind the tab run.

The Solvency tab has to put its page-turn buttons INTO the tab run rather than
before or after it, because the pilot sits just ahead of the Credit Cards tab
by decision. It did that by slicing the run into pieces and reassembling them:
`[:2]` for the tabs before the pilots, `[2:3]` for Credit Cards and `[-1:]`
for Archive. Five tabs, four positions covered, with nothing anywhere
saying so.
The Graph tab was simply not in that tab's ring, which is not a wrong order but
a SKIPPED control: the ring jumps a button plainly on screen.

`stops_before` exists so the run is never cut up. It takes the whole run and
inserts, so everything handed in comes back out. That property is what these
assert, since it is the one the slices could not state.
"""

from clear_budget.ui.utils.tab_icons import CREDIT_CARDS_TAB, TAB_SPECS, stops_before

_RUN = ["monthly", "solvency", "cards", "graph"]
_PILOTS = ["turn the page"]


class TestNothingIsEverDropped:
    """The property the hand-sliced version could not state."""

    def test_every_stop_handed_in_comes_back_out(self):
        result = stops_before(_RUN, "cards", _PILOTS)
        assert set(_RUN) <= set(result)
        assert len(result) == len(_RUN) + len(_PILOTS)

    def test_that_holds_when_the_marker_is_absent(self):
        """The marker is the CURRENT tab on that page, filtered out already."""
        result = stops_before(_RUN, "archive", _PILOTS)
        assert set(_RUN) <= set(result)
        assert result == _RUN + _PILOTS

    def test_an_empty_run_still_carries_the_extras(self):
        assert stops_before([], "cards", _PILOTS) == _PILOTS


class TestWhereTheExtrasLand:
    """Order matters as much as membership: the ring follows the drawing."""

    def test_extras_go_immediately_before_the_marker(self):
        assert stops_before(_RUN, "cards", _PILOTS) == [
            "monthly",
            "solvency",
            "turn the page",
            "cards",
            "graph",
        ]

    def test_the_run_keeps_its_own_order(self):
        result = stops_before(_RUN, "cards", _PILOTS)
        assert [stop for stop in result if stop in _RUN] == _RUN

    def test_no_extras_leaves_the_run_exactly_as_it_was(self):
        assert stops_before(_RUN, "cards", []) == _RUN

    def test_the_input_is_not_mutated(self):
        run = list(_RUN)
        stops_before(run, "cards", _PILOTS)
        assert run == _RUN


def test_the_named_tab_is_one_the_strip_actually_has():
    """The name is looked up in the strip, so a typo cannot pass unnoticed."""
    assert CREDIT_CARDS_TAB in [name for _spec, name in TAB_SPECS]
