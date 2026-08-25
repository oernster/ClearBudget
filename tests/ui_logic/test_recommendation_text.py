"""Tests for the Recommendations wording and row building (Qt-free)."""

from clear_budget.domain.services.recommendations import (
    KIND_BILL,
    KIND_INCOME,
    TimingMove,
    TrialDay,
)
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.domain.services.recommendations import (
    IncomeAsk,
    MonthOutlook,
    Recommendations,
)
from clear_budget.domain.services.recommendations import MonthLift, ReservePause
from clear_budget.ui.utils.recommendation_text import (
    HEADROOM_ITEM_CAP,
    headroom_rows,
    join_clauses,
    move_rows,
    panel_html,
    pause_html,
    pause_price_html,
    pause_rows,
    sooner_note_html,
)

_NAMES = {
    3: "March",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def _month_name(year: int, month: int) -> str:
    return f"{_NAMES[month]} {year}"


def _move(
    month,
    name="Rent",
    kind=KIND_BILL,
    from_day=14,
    to_day=21,
    before=-10000,
    after=5000,
):
    return TimingMove(
        year=2026,
        month=month,
        name=name,
        kind=kind,
        from_day=from_day,
        to_day=to_day,
        low_before_pence=before,
        low_after_pence=after,
    )


class TestJoinClauses:
    def test_shapes(self) -> None:
        assert join_clauses([]) == ""
        assert join_clauses(["a"]) == "a"
        assert join_clauses(["a", "b"]) == "a and b"
        assert join_clauses(["a", "b", "c"]) == "a, b and c"


class TestMoveRows:
    def test_a_single_move_reads_as_one_sentence(self) -> None:
        ((trial, html),) = move_rows([_move(10)], _month_name)
        assert trial == TrialDay(KIND_BILL, "Rent", 21)
        assert "in October 2026: lifts that month's low" in html

    def test_same_retiming_across_months_is_said_once(self) -> None:
        ((trial, html),) = move_rows([_move(10), _move(11)], _month_name)
        assert "from October 2026 onward" in html
        assert "October 2026's low" in html
        assert "and November 2026's low" in html

    def test_differing_days_share_a_row_but_not_a_sentence(self) -> None:
        ((trial, html),) = move_rows([_move(10), _move(11, to_day=22)], _month_name)
        # One row (one checkbox, one action) carrying both sentences; the
        # trial day is the later target, the one that satisfies both months.
        assert trial.to_day == 22
        assert "onward" not in html
        assert html.count("<p>") == 2

    def test_different_items_get_their_own_rows(self) -> None:
        rows = move_rows(
            [_move(10), _move(11, name="Pay", kind=KIND_INCOME, to_day=1)],
            _month_name,
        )
        assert [t.name for t, _ in rows] == ["Rent", "Pay"]
        assert "income <b>Pay</b>" in rows[1][1]


class TestHeadroomRows:
    def test_items_already_mandatory_are_excluded(self) -> None:
        extras = [_move(9), _move(9, name="Sub", from_day=5)]
        rows = headroom_rows(extras, [_move(10)], _month_name)
        assert [t.name for t, _ in rows] == ["Sub"]

    def test_ranked_by_total_lift_and_capped(self) -> None:
        extras = [
            _move(9, name=f"Bill{i}", before=0, after=1000 * i) for i in range(1, 6)
        ]
        rows = headroom_rows(extras, [], _month_name)
        assert len(rows) == HEADROOM_ITEM_CAP
        assert [t.name for t, _ in rows] == ["Bill5", "Bill4", "Bill3"]


class TestSoonerNote:
    def test_present_with_numbers_from_the_matching_extra(self) -> None:
        extras = [_move(9, before=40279, after=90279)]
        note = sooner_note_html([_move(10)], extras, YearMonth(2026, 9), _month_name)
        assert note is not None
        assert "in September 2026, say" in note
        assert "lifts that month's low from £402.79 to £902.79" in note

    def test_present_without_numbers_when_nothing_matches(self) -> None:
        note = sooner_note_html([_move(10)], [], YearMonth(2026, 9), _month_name)
        assert note is not None
        assert "Measured" not in note

    def test_extras_from_later_months_lend_no_numbers(self) -> None:
        extras = [_move(11, name="Rent")]
        note = sooner_note_html([_move(10)], extras, YearMonth(2026, 9), _month_name)
        assert "Measured" not in note

    def test_absent_when_the_first_month_already_moves(self) -> None:
        moves = [_move(9), _move(10)]
        assert sooner_note_html(moves, [], YearMonth(2026, 9), _month_name) is None

    def test_absent_with_no_moves(self) -> None:
        assert sooner_note_html([], [], YearMonth(2026, 9), _month_name) is None


def _result(lows, asks_pence=()):
    """A result whose UNAIDED lows are `lows`; asked months clamp to zero."""
    outlook = tuple(
        MonthOutlook(
            year=2026,
            month=9 + i,
            low_pence=max(low, 0),
            unaided_low_pence=low,
            low_day=14,
            close_pence=low,
        )
        for i, low in enumerate(lows)
    )
    asks = tuple(
        IncomeAsk(year=2026, month=11, amount_pence=p, by_day=28) for p in asks_pence
    )
    return Recommendations(moves=(), asks=asks, outlook=outlook)


class TestPanelHtml:
    def test_bullets_each_lifted_month_and_the_falling_ask(self) -> None:
        html = panel_html(
            _result([110000, 49792], asks_pence=[13895]),
            _result([-23408, 49792], asks_pence=[28895]),
            _month_name,
        )
        # One bullet per figure rather than a running sentence; unaided
        # lows, so the panel's numbers match the sentences above it
        # (October's -£234.08 is the number the move sentence quotes).
        assert "<p>With this change:</p><ul>" in html
        assert "<li>September 2026's low: from -£234.08 to £1,100.00</li>" in html
        assert "October" not in html  # unchanged months stay unsaid
        assert (
            "<li>Extra income these months still need to find: from"
            " £288.95 to £138.95</li>" in html
        )
        assert "Preview only; nothing is applied." in html

    def test_an_ask_cleared_entirely_reads_as_nothing(self) -> None:
        html = panel_html(
            _result([10000]),
            _result([10000], asks_pence=[5000]),
            _month_name,
        )
        assert "from £50.00 to nothing" in html

    def test_a_superseded_change_says_so(self) -> None:
        html = panel_html(_result([10000]), _result([10000]), _month_name)
        assert "adds nothing further" in html
        assert "Preview only; nothing is applied." in html


# ---- the third lever ---------------------------------------------------------
_CHRISTMAS = ReservePause(
    name="Christmas",
    from_year=2026,
    from_month=10,
    lifts=(
        MonthLift(year=2026, month=10, low_before_pence=50226, low_after_pence=60226),
        MonthLift(year=2026, month=11, low_before_pence=6226, low_after_pence=16226),
    ),
    shortfall_pence=40000,
    due_year=2026,
    due_month=12,
    due_within_horizon=True,
)


class TestAPauseSentence:
    def test_it_names_the_commitment_and_the_month_it_starts_from(self) -> None:
        html = pause_html(_CHRISTMAS, _month_name)
        assert "Pause setting aside for <b>Christmas</b> from October 2026" in html

    def test_it_lists_every_month_it_lifts_with_both_figures(self) -> None:
        html = pause_html(_CHRISTMAS, _month_name)
        assert "October 2026's low from £502.26 to £602.26" in html
        assert "November 2026's low from £62.26 to £162.26" in html

    def test_it_states_the_price_in_the_same_breath(self) -> None:
        """The sentence must not be readable as a free win."""
        assert "December 2026 then arrives <b>£400.00</b> short." in pause_html(
            _CHRISTMAS, _month_name
        )

    def test_a_due_month_beyond_the_window_says_so(self) -> None:
        """Otherwise the page shows all the relief and none of the cost."""
        beyond = ReservePause(
            name=_CHRISTMAS.name,
            from_year=_CHRISTMAS.from_year,
            from_month=_CHRISTMAS.from_month,
            lifts=_CHRISTMAS.lifts,
            shortfall_pence=_CHRISTMAS.shortfall_pence,
            due_year=2027,
            due_month=3,
            due_within_horizon=False,
        )
        assert "which is past this window" in pause_html(beyond, _month_name)

    def test_a_due_month_inside_the_window_does_not(self) -> None:
        assert "past this window" not in pause_html(_CHRISTMAS, _month_name)


class TestAPauseRow:
    def test_the_trial_names_the_commitment_and_its_start(self) -> None:
        ((trial, _html, _price),) = pause_rows((_CHRISTMAS,), _month_name)
        assert (trial.name, trial.from_year, trial.from_month) == (
            "Christmas",
            2026,
            10,
        )

    def test_the_trial_keys_the_way_a_retiming_does(self) -> None:
        """The page identifies a ticked change by (kind, name), whatever it is."""
        ((trial, _html, _price),) = pause_rows((_CHRISTMAS,), _month_name)
        assert (trial.kind, trial.name) == ("pause", "Christmas")


class TestThePricePanel:
    def test_it_says_the_change_finds_no_money(self) -> None:
        assert "finds no money" in pause_price_html(_CHRISTMAS, _month_name)

    def test_it_names_the_month_and_what_it_would_be_short(self) -> None:
        price = pause_price_html(_CHRISTMAS, _month_name)
        assert "December 2026 would arrive <b>£400.00</b> short" in price

    def test_a_preview_showing_only_relief_still_carries_the_price(self) -> None:
        """The failure this exists to prevent: a lever previewing as a gift."""
        html = panel_html(
            _result([10000]),
            _result([20000]),
            _month_name,
            price=pause_price_html(_CHRISTMAS, _month_name),
        )
        assert "low: from" in html
        assert "finds no money" in html

    def test_a_change_that_adds_nothing_further_still_carries_it(self) -> None:
        html = panel_html(
            _result([10000]),
            _result([10000]),
            _month_name,
            price=pause_price_html(_CHRISTMAS, _month_name),
        )
        assert "adds nothing further" in html
        assert "finds no money" in html
