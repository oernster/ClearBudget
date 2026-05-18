"""Amount value object  -  non-negative currency in pence."""

from dataclasses import dataclass

from clear_budget.shared.errors import InvalidAmountError


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
        """Format as £X.XX."""
        return f"£{self.pounds:.2f}"

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
