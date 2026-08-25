"""Tests for the Recommendations wording and row building (Qt-free)."""

from clear_budget.domain.services.recommendations import (
    KIND_BILL,
    KIND_INCOME,
    TimingMove,
    TrialDay,
)
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils.recommendation_text import (
    HEADROOM_ITEM_CAP,
    headroom_rows,
    join_clauses,
    move_rows,
    sooner_note_html,
    tried_caption,
)

_NAMES = {9: "September", 10: "October", 11: "November"}


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


class TestTriedCaption:
    def test_names_the_trial_and_the_entered_day(self) -> None:
        caption = tried_caption(KIND_BILL, "Rent", 14, 21)
        assert "Trying the bill <b>Rent</b> on day 21" in caption
        assert "entered as day 14" in caption
        assert "Nothing is applied" in caption
