"""A range of months exported as a FOLDER: one page each, plus an index.

The single-month export answers "how did March go" and the projection answers
"where is this heading". Neither answers "show me the year", which is what a
package is: the projection as the front page, then every month it covers as
its own page, linked from the row that summarises it.

WHAT THIS CHANGES, stated plainly because it is an invariant and not a detail.
Every report this application wrote until now referenced nothing outside
itself: no image, no stylesheet, no link, so the file survived being emailed
on its own. A package cannot hold to that, because an index whose rows lead
nowhere is a worse report than the projection it was built from. The rule
becomes one step wider and no wider: THE PACKAGE is self-contained. Every
page still carries its own styles and its own charts inline; the only outward
references any of them make are to siblings in the same folder, by bare
filename. Move the folder and it still works; move one page out of it
and only the link home is lost. `tests/application/reporting/test_reports.py`
pins both halves: the standalone exports still reference nothing at all.

Filenames are ISO-ish (`2026-03.html`), so a folder listing sorts into
calendar order in any file manager without the index being open.

Pure string building: no Qt, no file access, no clock. The caller writes the
files, which is what keeps this layer testable without a filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass

from clear_budget.application.reporting.month_report import month_report_html
from clear_budget.application.reporting.projection_report import (
    projection_report_html,
)

INDEX_NAME = "index.html"

_MONTH_TITLE = "{label}: bank balance by day"
_MONTH_SUBTITLE = "Projected day by day across {label}."
_INDEX_SUBTITLE = "{first} to {last}, with a page for every month."


@dataclass(frozen=True, slots=True)
class PackageFile:
    """One file of the package: its name inside the folder and its markup.

    A name rather than a path: the package is flat by design, so a caller
    joining this to a directory cannot be tricked into writing outside it.
    """

    name: str
    html: str


def month_page_name(year: int, month: int) -> str:
    """The filename one month's page takes inside the package."""
    return f"{year:04d}-{month:02d}.html"


def build_package(
    *,
    title: str,
    months,
    series_by_month,
    recorded_balance_pence: int | None = None,
) -> tuple[PackageFile, ...]:
    """Render a month range as an index plus one page per month.

    Args:
        title: Heading for the index, e.g. "Bank balance projection".
        months: ProjectionMonth values, ascending, as the projection report
            takes them.
        series_by_month: {(year, month): series} for the day-by-day page of
            each month. A month with no series still gets its row on the
            index; it simply gets no page and no link, which is the honest
            outcome when a month cannot be plotted.
        recorded_balance_pence: The bank balance the projection was chained
            from, stated on the index exactly as the standalone report states
            it.

    Returns the index first, then the month pages in calendar order.
    """
    projected = list(months)
    if not projected:
        index = projection_report_html(
            title=title,
            subtitle=_INDEX_SUBTITLE.format(first="No", last="months"),
            months=[],
        )
        return (PackageFile(INDEX_NAME, index),)

    pages: list[PackageFile] = []
    links: dict[str, str] = {}
    for month in projected:
        series = (series_by_month or {}).get((month.year, month.month))
        if not series:
            continue
        name = month_page_name(month.year, month.month)
        links[month.label] = name
        pages.append(
            PackageFile(
                name,
                month_report_html(
                    title=_MONTH_TITLE.format(label=month.label),
                    subtitle=_MONTH_SUBTITLE.format(label=month.label),
                    series=series,
                    floor_pence=month.floor_pence,
                    home_link=INDEX_NAME,
                ),
            )
        )

    index = projection_report_html(
        title=title,
        subtitle=_INDEX_SUBTITLE.format(
            first=projected[0].label, last=projected[-1].label
        ),
        months=projected,
        recorded_balance_pence=recorded_balance_pence,
        month_links=links,
    )
    return (PackageFile(INDEX_NAME, index), *pages)


def package_folder_name(months) -> str:
    """A folder name naming the range it holds, sortable and unambiguous."""
    projected = list(months)
    if not projected:
        return "clearbudget-months"
    first, last = projected[0], projected[-1]
    return (
        f"clearbudget-{first.year:04d}-{first.month:02d}"
        f"-to-{last.year:04d}-{last.month:02d}"
    )
