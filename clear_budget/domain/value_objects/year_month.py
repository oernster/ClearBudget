"""YearMonth value object  -  YYYY-MM string with validation and arithmetic."""

from dataclasses import dataclass
from datetime import datetime

from clear_budget.shared.errors import InvalidYearMonthError


@dataclass(frozen=True, slots=True)
class YearMonth:
    """Year-month value object in YYYY-MM format.

    Provides validated parsing, arithmetic (next/previous month), and comparison.
    """

    year: int
    month: int

    def __post_init__(self) -> None:
        """Validate year and month are in valid ranges."""
        if not 1 <= self.month <= 12:
            raise InvalidYearMonthError(f"Month must be 1-12, got {self.month}")
        if self.year < 1900 or self.year > 2100:
            raise InvalidYearMonthError(f"Year must be 1900-2100, got {self.year}")

    @classmethod
    def parse(cls, s: str) -> "YearMonth":
        """Parse YYYY-MM string."""
        try:
            parts = s.strip().split("-")
            if len(parts) != 2:
                raise ValueError("Invalid format")
            year = int(parts[0])
            month = int(parts[1])
            return cls(year=year, month=month)
        except (ValueError, IndexError) as e:
            raise InvalidYearMonthError(f"Invalid YearMonth format: {s!r}") from e

    @classmethod
    def today(cls) -> "YearMonth":
        """Get current year-month."""
        now = datetime.now()
        return cls(year=now.year, month=now.month)

    def __str__(self) -> str:
        """Format as YYYY-MM."""
        return f"{self.year:04d}-{self.month:02d}"

    def __repr__(self) -> str:
        return f"YearMonth({self})"

    def next_month(self) -> "YearMonth":
        """Return next month."""
        if self.month == 12:
            return YearMonth(year=self.year + 1, month=1)
        return YearMonth(year=self.year, month=self.month + 1)

    def previous_month(self) -> "YearMonth":
        """Return previous month."""
        if self.month == 1:
            return YearMonth(year=self.year - 1, month=12)
        return YearMonth(year=self.year, month=self.month - 1)

    def add_months(self, count: int) -> "YearMonth":
        """Add/subtract months (negative count goes backwards)."""
        total_months = self.year * 12 + self.month + count
        new_year = (total_months - 1) // 12
        new_month = ((total_months - 1) % 12) + 1
        return YearMonth(year=new_year, month=new_month)

    def __lt__(self, other: "YearMonth") -> bool:
        if not isinstance(other, YearMonth):
            return NotImplemented
        return (self.year, self.month) < (other.year, other.month)

    def __le__(self, other: "YearMonth") -> bool:
        if not isinstance(other, YearMonth):
            return NotImplemented
        return (self.year, self.month) <= (other.year, other.month)

    def __gt__(self, other: "YearMonth") -> bool:
        if not isinstance(other, YearMonth):
            return NotImplemented
        return (self.year, self.month) > (other.year, other.month)

    def __ge__(self, other: "YearMonth") -> bool:
        if not isinstance(other, YearMonth):
            return NotImplemented
        return (self.year, self.month) >= (other.year, other.month)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, YearMonth):
            return NotImplemented
        return (self.year, self.month) == (other.year, other.month)

    def __hash__(self) -> int:
        return hash((self.year, self.month))
