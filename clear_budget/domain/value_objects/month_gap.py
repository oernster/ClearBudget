"""MonthGap value object  -  what a month costs against what it brings in.

The Solvency page is good at saying a month does not hold together. This is
the figure that says by HOW MUCH, which is the one a person can act on: what
a month's full bank bills and its full reserves cost against its full income.

Reserves count because they are money the month genuinely has to find. A
month that pays every bill and sets aside nothing toward the car insurance is
not holding flat; it is borrowing from a future month that will have to find
the whole sum at once. Counting only the bills said that month was fine.

Deliberately whole-month arithmetic on both sides, unaffected by how far
through the month it is. "What does a month like this need" is a structural
question about the shape of the month rather than a question about today, so
the answer must not move simply because time passed. The still-due figures and
the projected close answer the other question and are shown beside it.

Card interest is carried alongside rather than folded in. It accrues on the
cards and never touches the bank account, so adding it to the bank gap would
overstate the gap by money that was never going to leave the account. Two
separate drains, reported as two separate figures.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonthGap:
    """One month's bank shortfall and its card interest, in pence.

    Attributes:
        income_pence: The month's total income.
        bank_bills_pence: The month's bills paid from the bank account.
        card_interest_pence: Interest accruing across the active cards this
            month. Never part of the bank gap.
        reserve_pence: What the month has to set aside toward commitments that
            fall outside it. Part of the bank gap, because it is money that
            has to be found from the same income the bills come out of. Zero
            when nothing is being set aside, which is every budget that does
            not use the Reserves page.
    """

    income_pence: int
    bank_bills_pence: int
    card_interest_pence: int
    reserve_pence: int = 0

    @property
    def needed_pence(self) -> int:
        """How much more the month needs to hold flat.

        Positive is a shortfall; zero or negative means income covers the
        bills and the reserves alike, the magnitude then being the headroom.
        """
        return self.bank_bills_pence + self.reserve_pence - self.income_pence

    @property
    def holds_flat(self) -> bool:
        """True when the month's income covers its bank bills and reserves."""
        return self.needed_pence <= 0

    def __str__(self) -> str:
        state = "holds flat" if self.holds_flat else f"needs {self.needed_pence}"
        return f"MonthGap({state}, card_interest={self.card_interest_pence})"
