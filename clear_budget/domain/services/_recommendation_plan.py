"""What the recommendation engine is given: a month's plan, day by day.

Split from `recommendations` so that module holds the reasoning and this one
holds the shape it reasons over. Re-exported from there, so nothing outside
imports this module by name.

A month carries two separate things and they must not be confused. Its ITEMS
move the balance: income arrives, bills leave. Its RESERVE does not; it is
what a day has already spoken for and must therefore keep. A day is judged on
the difference between them, which is why the reserve sits beside the items
rather than among them: adding it as an item would report an overdraft that
never happens, since the money is still in the account.
"""

from __future__ import annotations

from dataclasses import dataclass

# What kind of entry a planned item is; a bill's amount is negative.
KIND_INCOME = "income"
KIND_BILL = "bill"

# A month's first day, where a movable income is proposed to arrive.
FIRST_DAY = 1


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
    """A month's bank-side entries, income listed before bills.

    `reserve_by_day` is what the month's commitments hold back on each of its
    days, one value per day from the first. Empty means nothing is set aside,
    which is how every budget read before the Reserves page existed and is
    what keeps this engine's older answers unchanged.
    """

    year: int
    month: int
    days: int
    items: tuple[PlannedItem, ...]
    reserve_by_day: tuple[int, ...] = ()

    def reserve_at(self, day: int) -> int:
        """What is held back on `day`; zero when the month sets nothing aside."""
        if not self.reserve_by_day or day > len(self.reserve_by_day):
            return 0
        return self.reserve_by_day[day - 1]


@dataclass(frozen=True, slots=True)
class PlannedReserve:
    """One commitment's hold-back across the horizon, plus what it is for.

    `by_day` holds one tuple per horizon month, in the months' own order,
    each the daily hold-back that commitment alone contributes. Carried apart
    from the months' totals because pausing is a per-commitment question: the
    summed figure cannot say whose money it is.

    `due_year` and `due_month` name when the money is actually wanted, which
    is what makes a pause priceable rather than merely appealing. They may
    fall outside the horizon; that is the case worth stating plainly, since
    the window then shows the relief and none of the cost.
    """

    name: str
    amount_pence: int
    by_day: tuple[tuple[int, ...], ...]
    due_year: int
    due_month: int
