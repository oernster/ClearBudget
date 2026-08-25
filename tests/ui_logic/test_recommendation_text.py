"""Tests for the Recommendations moves wording (Qt-free)."""

from clear_budget.domain.services.recommendations import (
    KIND_BILL,
    KIND_INCOME,
    TimingMove,
)
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils.recommendation_text import (
    join_clauses,
    moves_html,
    sooner_note_html,
)

_NAMES = {9: "September", 10: "October", 11: "November"}


def _month_name(year: int, month: int) -> str:
    return f"{_NAMES[month]} {year}"


def _move(month, name="Rent", kind=KIND_BILL, from_day=14, to_day=21):
    return TimingMove(
        year=2026,
        month=month,
        name=name,
        kind=kind,
        from_day=from_day,
        to_day=to_day,
        low_before_pence=-10000,
        low_after_pence=5000,
    )


class TestJoinClauses:
    def test_shapes(self) -> None:
        assert join_clauses([]) == ""
        assert join_clauses(["a"]) == "a"
        assert join_clauses(["a", "b"]) == "a and b"
        assert join_clauses(["a", "b", "c"]) == "a, b and c"


class TestMovesHtml:
    def test_a_single_move_reads_as_before(self) -> None:
        (part,) = moves_html([_move(10)], _month_name)
        assert "in October 2026: lifts that month's low" in part

    def test_same_retiming_across_months_is_said_once(self) -> None:
        parts = moves_html([_move(10), _move(11)], _month_name)
        assert len(parts) == 1
        assert "from October 2026 onward" in parts[0]
        assert "October 2026's low" in parts[0]
        assert "and November 2026's low" in parts[0]

    def test_differing_days_fall_back_to_one_sentence_per_month(self) -> None:
        parts = moves_html([_move(10), _move(11, to_day=22)], _month_name)
        assert len(parts) == 2
        assert all("onward" not in p for p in parts)

    def test_different_items_never_share_a_sentence(self) -> None:
        parts = moves_html(
            [_move(10), _move(11, name="Pay", kind=KIND_INCOME, to_day=1)],
            _month_name,
        )
        assert len(parts) == 2
        assert "income <b>Pay</b>" in parts[1]


class TestSoonerNote:
    def test_present_when_no_move_starts_at_the_horizon(self) -> None:
        note = sooner_note_html([_move(10)], YearMonth(2026, 9), _month_name)
        assert note is not None
        assert "in September 2026, say" in note

    def test_absent_when_the_first_month_already_moves(self) -> None:
        moves = [_move(9), _move(10)]
        assert sooner_note_html(moves, YearMonth(2026, 9), _month_name) is None

    def test_absent_with_no_moves(self) -> None:
        assert sooner_note_html([], YearMonth(2026, 9), _month_name) is None
