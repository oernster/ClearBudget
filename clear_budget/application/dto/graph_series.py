"""GraphSeries DTO - one labelled day-by-day pence series for the month graph."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GraphSeries:
    """A labelled series of day-end values across one month.

    Attributes:
        label: Display name for the series (account or card name).
        values: One signed pence value per day of the month, index 0 = day 1.
    """

    label: str
    values: tuple[int, ...]
