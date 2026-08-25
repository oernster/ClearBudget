"""Recommendations: what would make the months ahead survivable.

Pure over its inputs: the caller hands in the months as planned and this
module answers with the smallest set of changes that clears them, in the
order a user should consider them. Free wins first, the ask last:

1. move a movable bill until after the month's last income has landed;
2. move a movable income to the start of its month;
3. whatever shortfall survives the best timing becomes an income ask.

Every suggestion is a re-run of the same day-by-day simulation the bank page
uses, reported with its measured effect, so nothing is proposed on a hunch: a
move that does not measurably lift the month's low is never emitted. A move
never changes what a month CLOSES at (its money still arrives and leaves
inside the month), so timing repairs the mid-month dip while the ask repairs
the structural deficit; the two are different problems and the output keeps
them separate.

Asks are INCREMENTAL: a month's ask assumes every earlier month's ask
arrived, so the amounts can be read as a plan ("find X by September, then Y
by October") and sum to the total the horizon needs.

No I/O, no clock, no Qt. The simulation mirrors the bank page's ordering
exactly: on a shared day income is received before bills are taken.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# What kind of entry a planned item is; a bill's amount is negative.
KIND_INCOME = "income"
KIND_BILL = "bill"

# A month's first day, where a movable income is proposed to arrive.
_FIRST_DAY = 1


@dataclass(frozen=True, slots=True)
class PlannedItem:
    """One dated entry in a month's plan, as the bank projection sees it."""

    name: str
    kind: str
    day: int
    amount_pence: int  # positive income, negative bank bill
    movable: bool


@dataclass(frozen=True, slots=True)
class PlannedMonth:
    """A month's bank-side entries, income listed before bills."""

    year: int
    month: int
    days: int
    items: tuple[PlannedItem, ...]


@dataclass(frozen=True, slots=True)
class TimingMove:
    """One retiming suggestion, with its measured effect on the month's low."""

    year: int
    month: int
    name: str
    kind: str
    from_day: int
    to_day: int
    low_before_pence: int
    low_after_pence: int


@dataclass(frozen=True, slots=True)
class IncomeAsk:
    """Extra money one month still needs after the best timing arrangement."""

    year: int
    month: int
    amount_pence: int
    by_day: int  # must have arrived on or before this day


@dataclass(frozen=True, slots=True)
class MonthOutlook:
    """Where one month lands once every suggestion above it is applied."""

    year: int
    month: int
    low_pence: int
    low_day: int
    close_pence: int


@dataclass(frozen=True, slots=True)
class Recommendations:
    """The full answer: moves, asks, the per-month picture and the extras.

    `extras` are OPTIONAL headroom moves: with every mandatory change applied,
    each is a further retiming that measurably lifts some month's low. None of
    them is needed to clear the target, which is why they are carried apart
    from `moves` and why `healthy` ignores them: a plan can be perfectly sound
    and still have cheap insurance on offer.
    """

    moves: tuple[TimingMove, ...]
    asks: tuple[IncomeAsk, ...]
    outlook: tuple[MonthOutlook, ...]
    extras: tuple[TimingMove, ...] = ()

    @property
    def healthy(self) -> bool:
        """Whether the plan as entered already clears the target everywhere."""
        return not self.moves and not self.asks


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


def retimed_months(
    months: tuple[PlannedMonth, ...], trials: tuple[TrialDay, ...]
) -> tuple[PlannedMonth, ...]:
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


def _low(opening_pence: int, month: PlannedMonth) -> tuple[int, int]:
    """The month's lowest balance and the day it lands on.

    A stable sort by day keeps the construction order on shared days; the
    construction order lists income first: on a shared day money is received
    before bills are taken, the same optimistic ordering the bank page uses.
    """
    balance = opening_pence
    low = opening_pence
    low_day = _FIRST_DAY
    for item in sorted(month.items, key=lambda entry: entry.day):
        balance += item.amount_pence
        if balance < low:
            low = balance
            low_day = item.day
    return low, low_day


def _close(opening_pence: int, month: PlannedMonth) -> int:
    """Where the month ends; timing moves inside the month cannot change it."""
    return opening_pence + sum(item.amount_pence for item in month.items)


def _last_income_day(month: PlannedMonth) -> int | None:
    """The day the month's last income lands; None in a month with none."""
    days = [item.day for item in month.items if item.amount_pence > 0]
    return max(days) if days else None


def _bill_move_candidate(
    month: PlannedMonth, item: PlannedItem, low_day: int
) -> int | None:
    """Where a movable bill could go, else None when moving cannot help.

    After the month's last income, capped at the month's end: a bill already
    due after every income is past the dip it could be moved over.
    """
    if item.kind != KIND_BILL or not item.movable or item.day > low_day:
        return None
    last_income = _last_income_day(month)
    if last_income is None:
        return None
    target = min(last_income + 1, month.days)
    if target <= item.day:
        return None
    return target


def _income_move_candidate(item: PlannedItem, low_day: int) -> int | None:
    """Where a movable income could go, else None when moving cannot help."""
    if item.kind != KIND_INCOME or not item.movable or item.day <= low_day:
        return None
    return _FIRST_DAY


def _retime(month: PlannedMonth, item: PlannedItem, to_day: int) -> PlannedMonth:
    """The month with one item moved to `to_day`."""
    moved = tuple(
        replace(entry, day=to_day) if entry is item else entry for entry in month.items
    )
    return replace(month, items=moved)


def _candidate_moves(
    opening_pence: int, month: PlannedMonth
) -> list[tuple[PlannedMonth, TimingMove]]:
    """Every single retiming that measurably lifts the month's low.

    Each candidate is evaluated by re-running the simulation, so every entry
    is a measurement rather than a heuristic. The survival loop picks the
    best of these; the headroom pass reports all of them.
    """
    low_before, low_day = _low(opening_pence, month)
    found: list[tuple[PlannedMonth, TimingMove]] = []
    for item in month.items:
        to_day = _bill_move_candidate(month, item, low_day)
        if to_day is None:
            to_day = _income_move_candidate(item, low_day)
        if to_day is None:
            continue
        candidate = _retime(month, item, to_day)
        low_after, _ = _low(opening_pence, candidate)
        if low_after <= low_before:
            continue
        move = TimingMove(
            year=month.year,
            month=month.month,
            name=item.name,
            kind=item.kind,
            from_day=item.day,
            to_day=to_day,
            low_before_pence=low_before,
            low_after_pence=low_after,
        )
        found.append((candidate, move))
    return found


def _best_move(
    opening_pence: int, month: PlannedMonth
) -> tuple[PlannedMonth, TimingMove] | None:
    """The single retiming that lifts the month's low the most, else None.

    Ties resolve by name so the result is stable run to run.
    """
    candidates = _candidate_moves(opening_pence, month)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda pair: (pair[1].low_after_pence, pair[1].name),
    )


def recommend(
    *,
    months: tuple[PlannedMonth, ...],
    opening_balance_pence: int,
    overdraft_limit_pence: int,
    buffer_pence: int,
) -> Recommendations:
    """The smallest measured set of changes that clears every month.

    A month is clear while its low stays at or above the target: the agreed
    overdraft floor plus the caller's emergency buffer. Moves are applied
    month by month until no move improves the low; whatever shortfall
    remains becomes that month's ask, assumed found before the next month is
    judged, so the asks read as an incremental plan.
    """
    target = buffer_pence - overdraft_limit_pence
    moves: list[TimingMove] = []
    asks: list[IncomeAsk] = []
    outlook: list[MonthOutlook] = []
    extras: list[TimingMove] = []
    balance = opening_balance_pence
    for month in months:
        current = month
        low, low_day = _low(balance, current)
        while low < target:
            improved = _best_move(balance, current)
            if improved is None:
                break
            current, move = improved
            moves.append(move)
            low, low_day = _low(balance, current)
        if low < target:
            shortfall = target - low
            asks.append(
                IncomeAsk(
                    year=current.year,
                    month=current.month,
                    amount_pence=shortfall,
                    by_day=low_day,
                )
            )
            balance += shortfall
            low += shortfall
        # The headroom pass: with the month's mandatory work applied, what
        # else would measurably lift its low. An item the survival loop
        # already moved yields no further candidate (its target day is
        # behind it), so an extra never duplicates a mandatory move.
        extras.extend(move for _, move in _candidate_moves(balance, current))
        outlook.append(
            MonthOutlook(
                year=current.year,
                month=current.month,
                low_pence=low,
                low_day=low_day,
                close_pence=_close(balance, current),
            )
        )
        balance = _close(balance, current)
    return Recommendations(
        moves=tuple(moves),
        asks=tuple(asks),
        outlook=tuple(outlook),
        extras=tuple(extras),
    )
