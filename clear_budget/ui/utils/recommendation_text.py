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
from clear_budget.domain.services.recommendations import KIND_BILL, TrialDay

# How many optional items are worth saying. Secondary and tertiary
# suggestions plus one: below this the lifts are noise beside the plan.
HEADROOM_ITEM_CAP = 3


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


def _group_html(group, month_name) -> str:
    """One item's sentences: the compact form while every month agrees.

    A group collapses to one sentence only while every month agrees on the
    days; a bill whose target day differs by month (the last income lands
    elsewhere) falls back to one sentence per month, because "from October
    onward" would then name a day November does not use.
    """
    uniform = all(
        (m.from_day, m.to_day) == (group[0].from_day, group[0].to_day) for m in group
    )
    if len(group) > 1 and uniform:
        return _group_move_html(group, month_name)
    return "".join(_single_move_html(m, month_name) for m in group)


def _row(group, month_name):
    """(TrialDay, sentence html) for one item's suggestion row.

    The trial day is the group's LATEST target day: a permanent change must
    satisfy every month that needs it and later months can only need later
    days (their last income lands later), so the latest is the one that
    holds everywhere.
    """
    first = group[0]
    to_day = max(m.to_day for m in group)
    return TrialDay(kind=first.kind, name=first.name, to_day=to_day), _group_html(
        group, month_name
    )


def move_rows(moves, month_name) -> list:
    """The mandatory section's rows, one per item rather than per month."""
    return [_row(group, month_name) for group in _grouped(moves)]


def headroom_rows(extras, moves, month_name) -> list:
    """The optional section's rows: the few best retimings nobody needs.

    Items already in the mandatory list are excluded (their story is told
    above, numbers included, by the sooner note); the rest rank by total
    measured lift across the horizon and only the top few are said, because
    on a healthy budget nearly everything movable helps a little and a page
    that lists all of it is a page nobody reads.
    """
    primary = {(m.kind, m.name) for m in moves}
    remaining = [m for m in extras if (m.kind, m.name) not in primary]
    groups = _grouped(remaining)
    groups.sort(key=lambda g: -sum(m.low_after_pence - m.low_before_pence for m in g))
    return [_row(group, month_name) for group in groups[:HEADROOM_ITEM_CAP]]


def ask_html(ask, month_name) -> str:
    """One month's ask, with the incremental reading stated beside it."""
    return (
        f"<p>Find <b>{money_from_pence(ask.amount_pence)}</b> by day"
        f" {ask.by_day} of {month_name(ask.year, ask.month)}."
        " Each ask assumes the earlier ones arrived, so together"
        " they are the whole plan.</p>"
    )


def outlook_html(month, month_name) -> str:
    """One outlook line: where the month lands with everything above it."""
    return (
        f"<p>{month_name(month.year, month.month)}: low of"
        f" {money_from_pence(month.low_pence)} on day {month.low_day},"
        f" closing at {money_from_pence(month.close_pence)}.</p>"
    )


def _effect_clauses(before_result, after_result, lead, month_name) -> list[str]:
    """The measured differences between two runs, as sentences; [] if none.

    Lows compare UNAIDED (no ask assumed), the same reading the suggestion
    sentences above the panel use, so a figure here always matches one the
    page already shows. The ask sentence names what the total is for: the
    extra income the shown months would need on top of these changes.
    """
    lifts = []
    for before, after in zip(before_result.outlook, after_result.outlook):
        if after.unaided_low_pence != before.unaided_low_pence:
            lifts.append(
                f"{month_name(after.year, after.month)}'s low goes from"
                f" {money_from_pence(before.unaided_low_pence)} to"
                f" {money_from_pence(after.unaided_low_pence)}"
            )
    parts = []
    if lifts:
        parts.append(f"{lead}, {join_clauses(lifts)}.")
    ask_before = sum(a.amount_pence for a in before_result.asks)
    ask_after = sum(a.amount_pence for a in after_result.asks)
    if ask_after != ask_before:
        falls_to = "nothing" if ask_after == 0 else money_from_pence(ask_after)
        verb = "falls" if ask_after < ask_before else "rises"
        parts.append(
            f"The extra income these months would still need to find {verb}"
            f" from {money_from_pence(ask_before)} to {falls_to}."
        )
    return parts


def panel_html(
    with_result, without_result, month_name, *, solo=None, baseline=None
) -> str:
    """A ticked row's tray panel: what this change contributes, measured.

    `with_result` is the pinned answer with every ticked change tried;
    `without_result` is the same set minus this row's change, so the panel
    states this change's MARGINAL effect however many boxes are ticked and
    in whatever order they were ticked. Two ticked changes can each make
    the other redundant (either alone parks the binding low at the month's
    end), so when the marginal is nil the panel falls back to the change's
    SOLO story against the as-entered baseline, then says the others cover
    it. The page copy above never moves; this panel is the only thing a
    tick paints.
    """
    parts = _effect_clauses(without_result, with_result, "With this change", month_name)
    if not parts and solo is not None and baseline is not None:
        parts = _effect_clauses(baseline, solo, "On its own", month_name)
        if parts:
            parts.append(
                "The other ticked changes already cover this, so together"
                " it adds nothing further."
            )
    if not parts:
        parts.append("With everything else ticked, this change adds nothing further.")
    parts.append("Preview only; nothing is applied.")
    return "<p>" + " ".join(parts) + "</p>"


def sooner_note_html(moves, extras, horizon_start, month_name) -> str | None:
    """The once-only note when no move is asked of the horizon's first month.

    Each move is listed in the month solvency first needs it, so a change
    that only becomes necessary in October reads as "leave September alone".
    It should not: a day changed for good changes every later month too and a
    month that already survives is not harmed, so making the change sooner is
    pure upside. The engine's headroom pass has already measured what the
    same retiming does in the earlier months, so the note carries numbers
    where a matching measurement exists. None while any move already starts
    at the horizon's first month, where the note would state nothing.
    """
    if not moves:
        return None
    earliest = min((m.year, m.month) for m in moves)
    if earliest <= (horizon_start.year, horizon_start.month):
        return None
    first = month_name(horizon_start.year, horizon_start.month)
    note = (
        "<p>Each move is shown in the month solvency first needs it. A day"
        " changed for good changes every later month too, so if you can make"
        f" the change sooner (in {first}, say) there is no reason not to."
    )
    payoffs = []
    for group in _grouped(moves):
        starts = min((m.year, m.month) for m in group)
        for extra in extras:
            if (extra.kind, extra.name) != (group[0].kind, group[0].name):
                continue
            if (extra.year, extra.month) >= starts:
                continue
            payoffs.append(
                f"moving <b>{extra.name}</b> in"
                f" {month_name(extra.year, extra.month)} lifts that month's"
                f" low from {money_from_pence(extra.low_before_pence)} to"
                f" {money_from_pence(extra.low_after_pence)}"
            )
    if payoffs:
        note += f" Measured, it pays straight away: {join_clauses(payoffs)}."
    return note + "</p>"
