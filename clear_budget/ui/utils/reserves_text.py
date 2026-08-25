"""Every user-visible string the Reserves page shows, in one place.

Qt-free on purpose, like `recommendation_text`: the sentences are pure string
work, so they can be read back in a test without a QApplication.

The register is the one the rest of the application keeps: short, declarative,
priced rather than flagged, with the assumptions stated in plain words. A
reserve is never encouraged and never congratulated; it is reported.
"""

from __future__ import annotations

TITLE = "Reserves"

BUFFER_LABEL = "Keep an emergency buffer of"
BUFFER_TOOLTIP = (
    "Held back on every day, on top of anything set aside below. The same"
    " buffer the Recommendations page aims at."
)

ADD_BUTTON = "Add a commitment"
EDIT_BUTTON = "Edit"
DELETE_BUTTON = "Delete"

TABLE_HEADINGS = (
    "Name",
    "Amount",
    "Due",
    "Repeats",
    "A month",
    "Held",
    "Still to find",
    "Active",
)

SECTION_WHAT_FOR = "What you are setting aside for"
SECTION_EVERYDAY = "Everyday spending"

EVERYDAY_UNSET = (
    "Not set. Every figure on every page assumes nothing leaves the account"
    " except the bills you have entered."
)
EVERYDAY_BUTTON = "Set an amount"
EVERYDAY_LATER = "Coming in a later release."

EMPTY_HEADING = "Nothing set aside."
EMPTY_BODY = (
    "Safe to Spend Today counts every penny above your buffer as spendable,"
    " including the money November's car insurance is already going to need."
)
EMPTY_PROMPT = "Add what is coming and the figure will tell you the truth about it."

FOOTER = (
    "A bill you pay once a year is not a surprise; it is a bill you have not"
    " been asked for yet. Setting it aside spreads it across the months before"
    " it lands, so the money it needs stops being counted as money you can"
    " spend. Nothing is moved anywhere and no separate account is assumed:"
    " this only changes what the app is willing to call spendable."
)


def verdict_line(*, total: str, count: int) -> str:
    """What is being held back, across how many commitments."""
    if count == 1:
        return f"{total} set aside across 1 commitment."
    return f"{total} set aside across {count} commitments."


def steep_note(*, monthly: str, natural: str, month_name: str) -> str:
    """Why the first cycle costs more a month than the years after it."""
    return (
        f"{monthly} a month because {month_name} is close."
        f" From next cycle it settles at {natural}."
    )


def repeats_label(*, months: int | None) -> str:
    """How often a commitment comes round, as a person would say it."""
    if months is None:
        return "Once"
    if months == 1:
        return "Monthly"
    months_in_year = 12
    if months == months_in_year:
        return "Annually"
    return f"Every {months} months"


def delete_question(*, name: str) -> str:
    """The confirmation shown before a commitment is removed for good."""
    return (
        f"Delete {name}? The months it has already run in lose the reserve"
        " they carried. Nothing else changes and no money moves."
    )
