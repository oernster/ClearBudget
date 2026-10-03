"""Amount value object  -  non-negative currency in pence."""

from dataclasses import dataclass

from clear_budget.shared.errors import InvalidAmountError

# The most one typed entry may hold: one billion in whole currency units.
# SQLite stores INTEGER as signed 64-bit (2**63 - 1 at most, about 9.2e18
# pence) and its SUM raises on overflow; the application adds amounts together
# (month totals, the balance, the applied log), so the cap sits far below that
# ceiling: tens of millions of entries at the cap still sum safely. It is also
# below 2**53, so pence divided by 100 still renders to the penny as a float.
MAX_AMOUNT_PENCE = 100_000_000_000


@dataclass(frozen=True, slots=True)
class Amount:
    """Non-negative GBP amount stored as integer pence.

    Stores as pence (integer) to avoid float rounding issues with money.
    """

    pence: int

    def __post_init__(self) -> None:
        """Validate amount is non-negative."""
        if self.pence < 0:
            raise InvalidAmountError("Amount cannot be negative")

    @classmethod
    def from_pounds(cls, pounds: float) -> "Amount":
        """Create Amount from pounds (float)."""
        pence = round(pounds * 100)
        return cls(pence=pence)

    @classmethod
    def zero(cls) -> "Amount":
        """Create zero amount."""
        return cls(pence=0)

    @property
    def pounds(self) -> float:
        """Return amount in pounds (float)."""
        return self.pence / 100

    def __str__(self) -> str:
        """Format as <symbol>X.XX using the active currency."""
        from clear_budget.shared.currency import get_symbol

        return f"{get_symbol()}{self.pounds:.2f}"

    def __repr__(self) -> str:
        return f"Amount({self.pounds:.2f})"

    def __add__(self, other: "Amount") -> "Amount":
        """Add two amounts."""
        if not isinstance(other, Amount):
            return NotImplemented
        return Amount(pence=self.pence + other.pence)

    def __mul__(self, scalar: float) -> "Amount":
        """Multiply amount by a scalar."""
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        return Amount(pence=round(self.pence * scalar))

    def __rmul__(self, scalar: float) -> "Amount":
        """Multiply amount by a scalar (reversed)."""
        return self.__mul__(scalar)

    def __lt__(self, other: "Amount") -> bool:
        """Compare amounts."""
        if not isinstance(other, Amount):
            return NotImplemented
        return self.pence < other.pence

    def __le__(self, other: "Amount") -> bool:
        """Compare amounts."""
        if not isinstance(other, Amount):
            return NotImplemented
        return self.pence <= other.pence

    def __gt__(self, other: "Amount") -> bool:
        """Compare amounts."""
        if not isinstance(other, Amount):
            return NotImplemented
        return self.pence > other.pence

    def __ge__(self, other: "Amount") -> bool:
        """Compare amounts."""
        if not isinstance(other, Amount):
            return NotImplemented
        return self.pence >= other.pence

    def __eq__(self, other: object) -> bool:
        """Compare amounts."""
        if not isinstance(other, Amount):
            return NotImplemented
        return self.pence == other.pence

    def __hash__(self) -> int:
        """Hash amount."""
        return hash(self.pence)
