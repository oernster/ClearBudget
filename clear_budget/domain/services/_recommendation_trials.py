"""Try-it-on: the plan with a change simulated, nothing written anywhere.

Split from `recommendations` so that module holds the reasoning; re-exported
from there, so nothing outside imports this module by name.

Two kinds of change can be tried. A TrialDay moves an item to a different day
of the month. A TrialPause stops setting money aside for one commitment from
a given month on. Both are pure rewrites of the plan handed in, which is what
lets the page preview a suggestion while applying none of it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# The trial kind a pause carries, so it keys alongside the retimings in a UI
# that identifies a trial by (kind, name).
KIND_PAUSE = "pause"


@dataclass(frozen=True, slots=True)
class TrialDay:
    """One try-it-on retiming: this item on this day, nowhere written.

    A trial is identified by what the user would actually change (the item
    and its new day), not by a month: a payment day changed in the real
    world changes every month at once, so the trial does too.
    """

    kind: str
    name: str
    to_day: int


@dataclass(frozen=True, slots=True)
class TrialPause:
    """One try-it-on pause: this commitment, set aside for no longer.

    Dated by the month it starts from, because that is the whole substance of
    the choice: pausing later relieves less and costs less. `kind` is fixed so
    a pause keys the same way a retiming does.
    """

    name: str
    from_year: int
    from_month: int
    kind: str = KIND_PAUSE


def retimed_months(months, trials):
    """The months with each trial's item on its trial day, where present.

    Pure and side-effect free: this is how the page previews a suggestion
    without applying anything. Only a movable item follows its trial (an
    immovable one has no business being tried; the guard makes a stale or
    hand-built trial harmless) and the day is capped at each month's length.
    """
    by_item = {(t.kind, t.name): t.to_day for t in trials}
    if not by_item:
        return months
    return tuple(
        replace(
            month,
            items=tuple(
                (
                    replace(item, day=min(by_item[(item.kind, item.name)], month.days))
                    if (item.kind, item.name) in by_item and item.movable
                    else item
                )
                for item in month.items
            ),
        )
        for month in months
    )


def immovable_months(months):
    """The months with every item pinned to its day.

    Fed to `recommend`, this yields the plan-free reading: no moves are
    proposed, the asks state what the months as given still need and the
    outlook shows where they land. The try-it-on panels are its caller:
    comparing two pinned runs isolates what the USER'S ticked changes do,
    where the normal run would hide them under the engine's own plan.
    """
    return tuple(
        replace(
            month,
            items=tuple(replace(item, movable=False) for item in month.items),
        )
        for month in months
    )


def paused_from(months, reserve, from_index: int):
    """The months with `reserve` no longer held back from `from_index` on.

    Only the hold-back changes. The items are untouched, so the balance walks
    exactly as it did: pausing frees what a day was keeping, it does not
    conjure money into the account.

    Never below zero. A day cannot release more than it is holding, so a
    reserve claiming a larger share than the month's total carries is capped
    rather than trusted; the alternative is a negative hold-back, which reads
    as free money and would price the pause as a gift.
    """
    return tuple(
        (
            month
            if index < from_index or not month.reserve_by_day
            else replace(
                month,
                reserve_by_day=tuple(
                    max(0, total - part)
                    for total, part in zip(month.reserve_by_day, reserve.by_day[index])
                ),
            )
        )
        for index, month in enumerate(months)
    )


def paused_months(months, reserves, trials):
    """The months with every trialled pause applied, in the trials' own terms.

    A pause names a commitment and a month; the reserve it refers to supplies
    the daily figures. A trial naming a commitment that is no longer set aside
    for is ignored rather than an error, on the same grounds a stale retiming
    is: a suggestion can outlive the thing it was about.
    """
    by_name = {reserve.name: reserve for reserve in reserves}
    for trial in trials:
        reserve = by_name.get(trial.name)
        if reserve is None:
            continue
        from_index = next(
            (
                index
                for index, month in enumerate(months)
                if (month.year, month.month) >= (trial.from_year, trial.from_month)
            ),
            None,
        )
        if from_index is None:
            continue
        months = paused_from(months, reserve, from_index)
    return months
