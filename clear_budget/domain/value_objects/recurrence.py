"""Recurrence value object  -  how often a commitment falls due."""

from __future__ import annotations

from dataclasses import dataclass

from clear_budget.shared.errors import InvalidCommitmentError

# Storage labels. `annual` is the twelve-month interval said the way a person
# says it; both forms parse and both mean the same interval, so the maths only
# ever reads `months`.
ONCE_LABEL = "once"
ANNUAL_LABEL = "annual"
EVERY_PREFIX = "months:"
MONTHS_IN_YEAR = 12


@dataclass(frozen=True, slots=True)
class Recurrence:
    """How often a commitment comes round again.

    Attributes:
        months: The interval in months; None when the commitment falls due
            once and never again.
    """

    months: int | None

    def __post_init__(self) -> None:
        """Reject an interval that could not describe a repeat."""
        if self.months is not None and self.months < 1:
            raise InvalidCommitmentError("Recurrence interval must be at least a month")

    @classmethod
    def once(cls) -> "Recurrence":
        """A commitment that falls due a single time."""
        return cls(months=None)

    @classmethod
    def annual(cls) -> "Recurrence":
        """The common case: once a year."""
        return cls(months=MONTHS_IN_YEAR)

    @classmethod
    def every_months(cls, months: int) -> "Recurrence":
        """A commitment falling due every `months` months."""
        return cls(months=months)

    @classmethod
    def parse(cls, text: str) -> "Recurrence":
        """Read a stored label back into a recurrence.

        Raises:
            InvalidCommitmentError: If the label is not one this understands.
        """
        if text == ONCE_LABEL:
            return cls.once()
        if text == ANNUAL_LABEL:
            return cls.annual()
        if text.startswith(EVERY_PREFIX):
            count = text[len(EVERY_PREFIX) :]
            if count.isdigit():
                return cls.every_months(int(count))
        raise InvalidCommitmentError(f"Unrecognised recurrence: {text!r}")

    @property
    def is_once(self) -> bool:
        """Whether this commitment never comes round again."""
        return self.months is None

    def __str__(self) -> str:
        """The storage label, normalised: a twelve-month interval is annual."""
        if self.months is None:
            return ONCE_LABEL
        if self.months == MONTHS_IN_YEAR:
            return ANNUAL_LABEL
        return f"{EVERY_PREFIX}{self.months}"
