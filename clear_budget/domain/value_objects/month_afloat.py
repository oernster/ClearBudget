"""MonthAfloat value object: what a month needs so the balance never breaches.

Its sibling MonthGap answers a structural question, what a month like this
costs against what it brings in; it deliberately knows nothing about the
balance the month opens with. That makes it useless as a rescue figure. A
month can need a great deal to hold flat and still be perfectly safe because
it opened with a cushion; another can need very little and still go under.
The Forward Projection blocks were stating the first number in a place a
reader takes for the second.

This is the second number, the only one a person can act on: how much
money has to arrive so the balance never drops below the floor at any point
in the month. It is read off the low point of the same day-by-day walk the
block prints above it, so the figure and the low it comes from can be checked
against each other by eye.

The floor is the agreed overdraft, not zero. A budget with no facility is
measured against zero, which is the same arithmetic with a limit of nothing.
Money already borrowed against an arranged facility is not a shortfall; the
account only breaches when it goes past what the bank has agreed to.

Whole-month; pointedly NOT cumulative across months. Each month is
measured on the projection as it stands, so the figure agrees with the
opening balance printed at the top of its own block. A November measured as
though October had already been rescued would contradict the "Opens" line
directly above it.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonthAfloat:
    """One month's distance from its overdraft floor, in pence.

    Attributes:
        low_point_pence: The lowest the balance gets at any point in the
            month, from the day-by-day walk. May be negative.
        overdraft_limit_pence: The agreed facility. Zero, the default, means
            no facility, so the floor is zero and any negative balance is a
            breach.
    """

    low_point_pence: int
    overdraft_limit_pence: int = 0

    @property
    def floor_pence(self) -> int:
        """The balance the month may not go below: the agreed overdraft."""
        return -self.overdraft_limit_pence

    @property
    def stays_afloat(self) -> bool:
        """True when the low point never breaches the floor."""
        return self.low_point_pence >= self.floor_pence

    @property
    def needed_pence(self) -> int:
        """How much must arrive to lift the low point up to the floor.

        Zero for a month that already stays afloat, rather than a negative
        number: a month with room to spare needs nothing; headroom is a
        different reading with its own property.
        """
        shortfall = self.floor_pence - self.low_point_pence
        return shortfall if shortfall > 0 else 0

    @property
    def headroom_pence(self) -> int:
        """How far the low point sits above the floor; zero when it breaches."""
        clear = self.low_point_pence - self.floor_pence
        return clear if clear > 0 else 0
