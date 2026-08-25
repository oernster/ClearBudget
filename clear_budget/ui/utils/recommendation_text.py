"""Wording for the Recommendations page's moves section.

Qt-free on purpose, like `tab_icons`: the sentences are pure string work, so
they can be tested without a QApplication.

The engine reasons per month and proposes the same retiming in every month
that needs it, which is correct arithmetic and odd reading: the action a user
actually takes is one call per bill, not one per month. So the SAME move
proposed across several months is said once ("from October onward") with its
per-month effects listed; one closing note says that a day changed for good
may change sooner than the first month that needs it, since a month that
already survives is not harmed by it.
"""

from __future__ import annotations

from clear_budget.application.formatting import money_from_pence
from clear_budget.domain.services.recommendations import KIND_BILL


def join_clauses(parts: list[str]) -> str:
    """Join list items the house way: commas, then a bare final "and"."""
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _grouped(moves) -> list[list]:
    """Moves grouped by the item they retime, keeping first-seen order."""
    groups: list[list] = []
    for move in moves:
        for group in groups:
            if (group[0].kind, group[0].name) == (move.kind, move.name):
                group.append(move)
                break
        else:
            groups.append([move])
    return groups


def _single_move_html(move, month_name) -> str:
    what = "bill" if move.kind == KIND_BILL else "income"
    return (
        f"<p>Move the {what} <b>{move.name}</b> from day"
        f" {move.from_day} to day {move.to_day} in"
        f" {month_name(move.year, move.month)}: lifts that"
        f" month's low from {money_from_pence(move.low_before_pence)}"
        f" to {money_from_pence(move.low_after_pence)}.</p>"
    )


def _group_move_html(group, month_name) -> str:
    """One retiming needed in several months, said as one action."""
    first = group[0]
    what = "bill" if first.kind == KIND_BILL else "income"
    effects = join_clauses(
        [
            f"{month_name(m.year, m.month)}'s low from"
            f" {money_from_pence(m.low_before_pence)} to"
            f" {money_from_pence(m.low_after_pence)}"
            for m in group
        ]
    )
    return (
        f"<p>Move the {what} <b>{first.name}</b> from day"
        f" {first.from_day} to day {first.to_day} from"
        f" {month_name(first.year, first.month)} onward: lifts {effects}.</p>"
    )


def moves_html(moves, month_name) -> list[str]:
    """The moves section's paragraphs, one per action rather than per month.

    A group collapses to one sentence only while every month agrees on the
    days; a bill whose target day differs by month (the last income lands
    elsewhere) falls back to one sentence per month, because "from October
    onward" would then name a day November does not use.
    """
    parts: list[str] = []
    for group in _grouped(moves):
        uniform = all(
            (m.from_day, m.to_day) == (group[0].from_day, group[0].to_day)
            for m in group
        )
        if len(group) > 1 and uniform:
            parts.append(_group_move_html(group, month_name))
        else:
            parts.extend(_single_move_html(m, month_name) for m in group)
    return parts


def sooner_note_html(moves, horizon_start, month_name) -> str | None:
    """The once-only note when no move is asked of the horizon's first month.

    Each move is listed in the month solvency first needs it, so a change
    that only becomes necessary in October reads as "leave September alone".
    It should not: a day changed for good changes every later month too and a
    month that already survives is not harmed, so making the change sooner is
    pure upside. None while any move already starts at the horizon's first
    month, where the note would state nothing.
    """
    if not moves:
        return None
    earliest = min((m.year, m.month) for m in moves)
    if earliest <= (horizon_start.year, horizon_start.month):
        return None
    first = month_name(horizon_start.year, horizon_start.month)
    return (
        "<p>Each move is shown in the month solvency first needs it. A day"
        " changed for good changes every later month too, so if you can make"
        f" the change sooner (in {first}, say) there is no reason not to.</p>"
    )
